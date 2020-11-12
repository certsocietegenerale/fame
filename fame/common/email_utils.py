import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from jinja2 import Environment, FileSystemLoader

from fame.core.config import Config
from fame.common.exceptions import MissingConfiguration


NAMED_CONFIG = {
    'email': {
        'description': 'For FAME to be able to send emails.',
        'config': [
            {
                'name': 'host',
                'type': 'str',
                'default': 'localhost',
                'description': 'Hostname or IP address of SMTP server'
            },
            {
                'name': 'port',
                'type': 'integer',
                'default': 25,
                'description': 'Port on which the SMTP server is listening'
            },
            {
                'name': 'username',
                'type': 'str',
                'default': '',
                'description': 'Username if SMTP server requires authentication'
            },
            {
                'name': 'password',
                'type': 'str',
                'default': '',
                'description': 'Password if SMTP server requires authentication'
            },
            {
                'name': 'tls',
                'type': 'bool',
                'default': False,
                'description': 'Use TLS to connect to SMTP server ?'
            },
            {
                'name': 'from_address',
                'type': 'str',
                'description': 'Email address used for "From"'
            },
            {
                'name': 'replyto',
                'type': 'str',
                'default': None,
                'description': 'Email address used for "Reply-to" if different from "From"'
            },
        ]
    }
}


class EmailMixin:
    named_configs = NAMED_CONFIG


class EmailMessage:
    def __init__(self, server, subject):
        self.server = server

        self.msg = MIMEMultipart()
        self.msg['Subject'] = subject
        self.msg['From'] = server.config.from_address
        self.msg['Reply-to'] = server.config.replyto or server.config.from_address
        self.msg['Return-path'] = server.config.replyto or server.config.from_address
        self.msg.preamble = subject

    def add_content(self, text, content_type="plain"):
        self.msg.attach(MIMEText(text, content_type, "utf-8"))

    def add_attachment(self, filepath, filename=None):
        if filename is None:
            filename = os.path.basename(filepath)

        with open(filepath, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
            part['Content-Disposition'] = 'attachment; filename="{0}"'.format(filename)
            self.msg.attach(part)

    def send(self, to, cc=[], bcc=[]):
        recipients = to + cc + bcc

        self.msg['To'] = ','.join(to)
        if cc:
            self.msg['Cc'] = ','.join(cc)
        if bcc:
            self.msg['Bcc'] = ','.join(bcc)

        self.server.smtp.sendmail(self.msg['From'], recipients, self.msg.as_string())


class EmailServer:
    def __init__(self, template_path=None):
        self.template_path = template_path
        self.env = None
        if self.template_path:
            self.env = Environment(loader=FileSystemLoader(template_path))

        try:
            self.config = Config.get(name="email").get_values()
            self.is_configured = True

            try:
                self.smtp = smtplib.SMTP(self.config.host, self.config.port)

                if self.config.tls:
                    self.smtp.ehlo()
                    self.smtp.starttls()

                if self.config.username and self.config.password:
                    self.smtp.login(self.config.username, self.config.password)
                    self.is_connected = True
                else:
                    status = self.smtp.noop()[0]
                    self.is_connected = (status == 250)
            except Exception as e:
                print(e)
                self.is_connected = False
        except MissingConfiguration:
            self.is_configured = False
            self.is_connected = False

    def new_message(self, subject, body):
        msg = EmailMessage(self, subject)
        msg.add_content(body)

        return msg

    def new_message_from_template(self, subject, template, context={}):
        if self.env:
            template = self.env.get_template(template)
            body = template.render(**context)
            msg = EmailMessage(self, subject)
            msg.add_content(body, 'html')

            return msg
        else:
            raise MissingConfiguration("No 'template_path' specified when EmailServer was created.")
