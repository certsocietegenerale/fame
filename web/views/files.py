from pymongo import DESCENDING
from flask import make_response, request, flash, redirect, abort
from flask_classful import FlaskView, route
from flask_paginate import Pagination
from flask_login import current_user
from werkzeug.utils import secure_filename

from fame.core.store import store
from fame.core.file import File
from fame.core.module_dispatcher import dispatcher
from web.views.negotiation import render, render_json
from web.views.constants import PER_PAGE
from web.views.helpers import (
    file_download,
    get_or_404,
    requires_permission,
    clean_files,
    clean_analyses,
    clean_users,
    enrich_comments,
    enrich_exists_on_fs,
    comments_enabled,
)
from web.views.mixins import UIView


def return_file(file):
    analyses = list(current_user.analyses.find({"_id": {"$in": file["file"]["analysis"]}}))
    file["av_modules"] = [m.name for m in dispatcher.get_antivirus_modules()]

    for analysis in analyses:
        if "analyst" in analysis:
            analyst = store.users.find_one({"_id": analysis["analyst"]})
            analysis["analyst"] = clean_users(analyst)

    file["file"]["analysis"] = clean_analyses(analyses)
    return render(
        file,
        "files/show.html",
        ctx={"data": file, "options": dispatcher.options, "comments_enabled": comments_enabled()},
    )


class FilesView(FlaskView, UIView):
    def index(self):
        """Get the list of objects.

        .. :quickref: File; Get the list of objects

        Response is paginated and will only contain 25 results. The most recent
        objects appear first.

        :query page: page number.
        :query filter: (optional) set filter. can be "to_review" or "reviewed"
        :type page: int

        :>json list files: list of files (see :http:get:`/files/(id)` for details on the format of a file).
        """
        page = int(request.args.get("page", 1))
        filter_arg = request.args.get('filter')
        filter_query = {}
        if current_user.has_permission('review'):
            if filter_arg == 'reviewed':
                filter_query = {"reviewed": { "$exists": True, "$nin": [None, False] } }
            elif filter_arg == 'to_review':
                filter_query = { "reviewed": { "$exists": True, "$eq": None } }

        files = current_user.files.find(filter_query).sort("_id", DESCENDING).limit(PER_PAGE).skip((page - 1) * PER_PAGE)
        pagination = Pagination(page=page, per_page=PER_PAGE, total=current_user.files.count_documents(filter_query), css_framework="bootstrap3")
        files = {"files": clean_files(list(files))}

        for f in files['files']:
            if 'reviewed' in f and f['reviewed']:
                reviewer = store.users.find_one({'_id': f['reviewed']})
                if reviewer:
                    f['reviewed'] = clean_users(reviewer)
                else:
                    f['reviewed'] = {'_id': None, "name": None}

        return render(files, "files/index.html", ctx={"data": files, "pagination": pagination, "filter": filter_arg})

    def get(self, id):
        """Get the object with `id`.

        .. :quickref: File; Get an object

        Resulting object is in the ``file`` field.

        :param id: id of the object.

        :>json dict _id: ObjectId dict.
        :>json string md5: MD5 hash.
        :>json string sha1: SHA1 hash.
        :>json string sha256: SHA256 hash.
        :>json string type: FAME type.
        :>json string mime: mime type.
        :>json string detailed_type: detailed type.
        :>json list groups: list of groups (as strings) that have access to this file.
        :>json list owners: list of groups (as strings) that submitted this file.
        :>json list probable_names: list of probable names (as strings).
        :>json list analysis: list of analyses' ObjectIds.
        :>json list parent_analyses: list of analyses (as ObjectIds) that extracted this object.
        :>json dict antivirus: dict with antivirus names as keys.
        :>json user reviewed: analyst's ObjectId if review has been performed
        :>json bool exists_on_disk: True if the file still exists on disk, False otherwise
        """
        file = {"file": enrich_comments(clean_files(enrich_exists_on_fs(get_or_404(current_user.files, _id=id))))}
        return return_file(file)

    @route("/hash/<file_hash>", methods=["GET"])
    def get_hash(self, file_hash):
        """Get the object with `file_hash`.

        .. :quickref: File; Get an object by a hash

        :param hash: hash of the object.

        :>json file file: list of files (see :http:get:`/files/(id)` for details on the format of a file).
        """
        hash_type = {64: "sha256", 40: "sha1", 32: "md5"}

        # If the hash has an unknown length, return 400
        if len(file_hash) not in hash_type:
            abort(400)

        hash_filter = {hash_type[len(file_hash)]: file_hash.lower()}
        return return_file({"file": enrich_comments(clean_files(enrich_exists_on_fs(get_or_404(current_user.files, **hash_filter))))})

    @route("/md5/<md5>", methods=["GET"])
    def get_md5(self, md5):
        """Get the object with `md5`.

        .. :quickref: File; Get an object by MD5

        :param md5: md5 of the object.

        :>json file file: list of files (see :http:get:`/files/(id)` for details on the format of a file).
        """
        return return_file({"file": enrich_comments(clean_files(enrich_exists_on_fs(get_or_404(current_user.files, md5=md5.lower()))))})

    @route("/sha1/<sha1>", methods=["GET"])
    def get_sha1(self, sha1):
        """Get the object with `sha1`.

        .. :quickref: File; Get an object by SHA1

        :param sha1: sha1 of the object.

        :>json file file: list of files (see :http:get:`/files/(id)` for details on the format of a file).
        """
        return return_file({"file": enrich_comments(clean_files(enrich_exists_on_fs(get_or_404(current_user.files, sha1=sha1.lower()))))})

    @route("/sha256/<sha256>", methods=["GET"])
    def get_sha256(self, sha256):
        """Get the object with `sha256`.

        .. :quickref: File; Get an object by SHA256

        :param sha256: sha256 of the object.

        :>json file file: list of files (see :http:get:`/files/(id)` for details on the format of a file).
        """
        return return_file(
            {"file": enrich_comments(clean_files(enrich_exists_on_fs(get_or_404(current_user.files, sha256=sha256.lower()))))}
        )

    @requires_permission("worker")
    def post(self):
        file = request.files["file"]
        via = request.form.get('via')

        f = File(filename=file.filename, stream=file.stream, submitted_via=via)

        return render_json({"file": f})

    @route("/<id>", methods=["DELETE"])
    @requires_permission("delete")
    def anonymize(self, id):
        """Anonymize (soft delete) a file from FAME disk. Support files from associated analyses are also removed, if any.

        .. :quickref: File; Anonymize (soft delete) an object.

        :param id: id of the file to anonymize.

        :>json string response: Contain information on the deletion status.
        """
        f = File(get_or_404(current_user.files, _id=id))
        if f:
            flash("File {} and associated analyses were deleted from disk.".format(id))
            f.delete(preserve_db=True)
            return {"response": "ok"}

        return {"response": "File not found"}

    def download(self, id):
        """Download the file with `id`.

        .. :quickref: File; Download a file

        :param id: id of the file to download.
        """
        f = File(get_or_404(current_user.files, _id=id))
        return file_download(f["filepath"])

    @route("/<id>/submit_to_av/<module>", methods=["POST"])
    def submit_to_av(self, id, module):
        """Submit a file to an Antivirus module.

        .. :quickref: File; Submit file to an antivirus module

        If succesful, the response will be ``"ok"``. Otherwise, it will be an
        error message.

        :param id: id of the file to submit.
        :param module: name of the module to submit the file to.
        """
        f = File(get_or_404(current_user.files, _id=id))

        for av_module in dispatcher.get_antivirus_modules():
            if av_module.name == module:
                av_module.submit(f["filepath"])
                f.update_value(["antivirus", module], True)
                break
        else:
            return make_response("antivirus module '{}' not present / enabled.".format(module))

        return make_response("ok")

    @route("/<id>/remove_group/", methods=["POST"])
    def remove_group(self, id):
        f = File(get_or_404(current_user.files, _id=id))

        group = request.form.get("group")

        if group in f["owners"]:
            flash("This group submitted this file themselves. You cannot neuralize them.", "danger")
        else:
            f.remove_group(group)

        return redirect(request.referrer)

    @route("/<id>/add_group/", methods=["POST"])
    def add_group(self, id):
        f = File(get_or_404(current_user.files, _id=id))
        group = request.form.get("group")

        f.add_groups([group])

        return redirect(request.referrer)

    @requires_permission("review")
    @route('/<id>/review', methods=["POST"])
    def review(self, id):
        """Set review value state of a file

        .. :quickref: File; set review state
        Set the review state of a file.

        :form bool reviewed: if the file has been reviewed or not
        """
        f = File(get_or_404(current_user.files, _id=id))
        reviewed = request.form.get('reviewed')
        if reviewed:
            f.review(current_user['_id'])
        else:
            f.review(None)

        return redirect(request.referrer)

    @route("/<id>/change_type/", methods=["POST"])
    def change_type(self, id):
        f = File(get_or_404(current_user.files, _id=id))
        new_type = request.form.get("type")

        f.update_value("type", new_type)

        return redirect(request.referrer)

    @route("/<id>/add_comment/", methods=["POST"])
    def add_comment(self, id):
        if comments_enabled():
            f = File(get_or_404(current_user.files, _id=id))

            if current_user.has_permission("add_probable_name"):
                probable_name = request.form.get("probable_name")
            else:
                probable_name = None

            comment = request.form.get("comment")
            analysis_id = request.form.get("analysis")
            notify = request.form.get("notify")

            if comment:
                # If there is an analysis ID, make sure it is accessible
                if analysis_id:
                    get_or_404(current_user.analyses, _id=analysis_id)

                f.add_comment(current_user["_id"], comment, analysis_id, probable_name, notify)
            else:
                flash("Comment should not be empty", "danger")

        return redirect(request.referrer)
