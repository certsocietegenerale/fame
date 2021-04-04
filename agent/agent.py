import os
import sys
import inspect
import importlib
import traceback
import collections
from uuid import uuid4
from tempfile import mkstemp
from shutil import copyfileobj
from typing import Optional, List, Dict
from multiprocessing import Queue, Process
from flask import Flask, jsonify, request, abort, make_response


AGENT_ROOT = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(AGENT_ROOT)

#
# Helpers
#


def is_iterable(element):
    return isinstance(element, collections.Iterable) and not isinstance(element, str)


def iterify(element):
    if is_iterable(element):
        return element
    else:
        return (element,)


#
# Local definition of IsolatedProcessingModule
#

class IsolatedExceptions:
    class ModuleInitializationError(Exception):
        def __init__(self, module, description):
            self._module = module.name
            self._description = description

        def __str__(self):
            return "%s" % (self._description)

    class ModuleExecutionError(Exception):
        def __init__(self, description):
            self._description = description

        def __str__(self):
            return self._description


class IsolatedModule:
    class IsolatedProcessingModule:
        name: Optional[str] = None
        config: List[Dict] = []

        def __init__(self):
            self._results = {
                'logs': [],
                'generated_files': {},
                'extracted_files': [],
                'support_files': {},
                'extractions': {},
                'probable_names': [],
                'iocs': {},
                'tags': [],
                'result': False
            }
            self.results = None
            self.should_restore = False

        def initialize(self):
            pass

        def __getattr__(self, name):
            self.log('error', "'{}' is not available in IsolatedProcessingModule".format(name))

        def log(self, level, message):
            self._results['logs'].append((level, message))

        def register_files(self, file_type, locations):
            if file_type not in self._results['generated_files']:
                self._results['generated_files'][file_type] = []

            for location in iterify(locations):
                self._results['generated_files'][file_type].append(location)

        def add_extracted_file(self, location):
            self._results['extracted_files'].append(location)

        def add_support_file(self, name, location):
            self._results['support_files'][name] = location

        def add_extraction(self, label, extraction):
            self._results['extractions'][label] = extraction

        def add_probable_name(self, probable_name):
            self._results['probable_names'].append(probable_name)

        def add_ioc(self, values, tags=[]):
            for value in iterify(values):
                self._results['iocs'][value] = tags

        def add_tag(self, tag):
            self._results['tags'].append(tag)

        def each_with_type(self, target, target_type):
            return self.each(target)

        def run_each_with_type(self, target, target_type):
            try:
                return self.each_with_type(target, target_type)
            except IsolatedExceptions.ModuleExecutionError as e:
                self.log("error", "Could not run on %s: %s" % (target, e))
                return False
            except Exception:
                tb = traceback.format_exc()
                self.log("error", "Could not run on %s.\n %s" % (target, tb))
                return False

        def to_dict(self):
            return {
                "results": self.results,
                "_results": self._results,
                "should_restore": self.should_restore
            }


class FakePackage:
    __path__: List[str] = []


def fake_module(path, klass):
    path_parts = path.split('.')

    for i in range(1, len(path_parts)):
        sys.modules['.'.join(path_parts[0:i])] = FakePackage

    sys.modules[path] = klass


fake_module('fame.core.module', IsolatedModule)
fake_module('fame.common.exceptions', IsolatedExceptions)


#
# Worker
#

def run_module(queue, module, target, file_type):
    if module.run_each_with_type(target, file_type):
        module._results['result'] = True

    queue.put(module.to_dict())


class Worker:
    def __init__(self):
        self.current_task = None
        self.module = None
        self.queue = None
        self._module_results = None

    def new_task(self):
        self.current_task = str(uuid4())
        return self.current_task

    def is_valid_task_id(self, task_id):
        return task_id is not None and task_id == self.current_task

    def set_module(self, name, config):
        if 'module' in sys.modules:
            module = importlib.reload(sys.modules['module'])
        else:
            module = importlib.import_module('module')

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.name and obj.name == name:
                self.queue = Queue()
                self.module = obj()
                self._module_results = None

                for key in config:
                    setattr(self.module, key, config[key])

                self.module.initialize()
                break

        return self.module

    def each(self, target, file_type):
        self.process = Process(target=run_module, args=(self.queue, self.module, target, file_type))
        self.process.start()

    def is_ready(self):
        if self.process.is_alive():
            return False
        else:
            self._module_results = self.queue.get(block=False)
            return True

    def get_results(self):
        return self._module_results


worker = Worker()


#
# Web Server
#

app = Flask(__name__)


def validate_task_id(task_id):
    if not worker.is_valid_task_id(task_id):
        abort(403)


@app.route('/ready')
def agent_ready():
    return jsonify({'status': 'ok'})


@app.route('/new_task')
def new_task():
    return jsonify({'task_id': worker.new_task()})


@app.route('/<task_id>/module_update', methods=['POST'])
def module_update(task_id):
    validate_task_id(task_id)

    file = request.files['file']

    filepath = os.path.join(AGENT_ROOT, 'module.py')

    with open(filepath, "wb") as fd:
        copyfileobj(file.stream, fd)

    return jsonify({'status': 'ok'})


@app.route('/<task_id>/module_update_info', methods=['POST'])
def module_update_info(task_id):
    validate_task_id(task_id)

    name = request.json['name']
    config = request.json['config']

    try:
        worker.set_module(name, config)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})


@app.route('/<task_id>/module_each/<file_type>', methods=['POST'])
def module_each(task_id, file_type):
    validate_task_id(task_id)

    file = request.files['file']
    fd, filepath = mkstemp()

    with os.fdopen(fd, "wb") as fd:
        copyfileobj(file.stream, fd)

    worker.each(filepath, file_type)

    return jsonify({'status': 'ok'})


@app.route('/<task_id>/ready')
def ready(task_id):
    validate_task_id(task_id)

    return jsonify({'ready': worker.is_ready()})


@app.route('/<task_id>/results')
def results(task_id):
    validate_task_id(task_id)

    return jsonify(worker.get_results())


@app.route('/<task_id>/get_file', methods=['POST'])
def get_file(task_id):
    validate_task_id(task_id)

    filepath = request.form.get('filepath')
    with open(filepath, 'rb') as fd:
        response = make_response(fd.read())

    response.headers["Content-Disposition"] = "attachment; filename='{0}'".format(os.path.basename(filepath))

    return response


if __name__ == '__main__':
    app.run(debug=False, port=4242, host="0.0.0.0")
