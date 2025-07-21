import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from tclogger import logger, logstr, dict_to_str, get_now_str, brk
from typing import TypedDict, Optional, Union, Literal
from pathlib import Path


class EmailConfigsType(TypedDict):
    smtp_server: str
    smtp_port: int
    username: str
    password: str


class EmailContentType(TypedDict):
    to: Union[str, list[str]]
    subject: str
    body: str
    cc: Optional[list[str]] = None
    attachments: Optional[list[Union[str, Path]]] = []
    mime_type: Optional[Literal["plain", "html"]] = "html"


class Emailer:
    def __init__(
        self,
        configs: EmailConfigsType,
        connect_at_init: bool = True,
        verbose: bool = True,
    ):
        self.configs = configs
        self.smtp_server = configs["smtp_server"]
        self.smtp_port = configs["smtp_port"]
        self.username = configs["username"]
        self.password = configs["password"]
        self.connect_at_init = connect_at_init
        self.verbose = verbose
        logger.enter_quiet(not self.verbose)
        self.smtp: Optional[smtplib.SMTP] = None
        if connect_at_init:
            self.connect()

    def connect(self) -> smtplib.SMTP:
        logger.note(f"> Connecting SMTP:")
        info_dict = {
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "username": self.username,
            "now": get_now_str(),
        }
        logger.mesg(dict_to_str(info_dict), indent=2)
        self.smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
        # context = ssl.create_default_context()
        # self.smtp.starttls(context=context)
        self.smtp.login(self.username, self.password)
        logger.okay(f"+ Connected SMTP: {logstr.file(brk(self.username))}")
        return self.smtp

    def disconnect(self):
        self.smtp.quit()
        logger.okay(f"- Disconnected SMTP: {logstr.file(brk(self.username))}")

    def mail_list_to_str(self, to: Union[str, list[str]]) -> str:
        if not to:
            return to
        if isinstance(to, str):
            return to
        if isinstance(to, (list, tuple)):
            return ", ".join(to)
        raise ValueError("Invalid type for 'to'. Expected str or list[str].")

    def attach_to_mime(self, attach: Union[str, Path]) -> MIMEBase:
        if not Path(attach).exists():
            logger.warn(f"  * Attachment not found: {logstr.file(brk(attach))}")
            return None
        part = MIMEBase("application", "octet-stream")
        with open(attach, "rb") as rf:
            part.set_payload(rf.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=Path(attach).name,
        )
        return part

    def attaches_to_mimes(
        self, attaches: Union[list[Union[str, Path]], Union[str, Path]]
    ) -> list[MIMEBase]:
        if isinstance(attaches, (str, Path)):
            attaches = [attaches]
        mime_attaches = []
        for attach in attaches:
            mime_attach = self.attach_to_mime(attach)
            if mime_attach:
                mime_attaches.append(mime_attach)
        return mime_attaches

    def content_to_mime_msg(self, content: EmailContentType) -> str:
        msg = MIMEMultipart()

        # from, to, subject
        msg["From"] = self.username
        msg["To"] = self.mail_list_to_str(content["to"])
        msg["Subject"] = content["subject"]

        # cc, bcc
        if content.get("cc"):
            msg["Cc"] = self.mail_list_to_str(content["cc"])

        if content.get("bcc"):
            msg["Bcc"] = self.mail_list_to_str(content["bcc"])

        # body
        mime_type = content.get("mime_type", "html")
        mime_body = MIMEText(content["body"], mime_type)
        msg.attach(mime_body)

        # attachments
        mime_attaches = self.attaches_to_mimes(content.get("attachments", []))
        for mime_attach in mime_attaches:
            msg.attach(mime_attach)

        return msg.as_string()

    def send(self, content: EmailContentType) -> dict:
        logger.note(f"> Sending email:")
        logger.mesg(dict_to_str(content), indent=2)
        msg = self.content_to_mime_msg(content)
        res = self.smtp.sendmail(self.username, content["to"], msg)
        logger.okay(dict_to_str(res), indent=2)
        return res

    def __del__(self):
        if self.smtp:
            self.disconnect()
        logger.exit_quiet(not self.verbose)
