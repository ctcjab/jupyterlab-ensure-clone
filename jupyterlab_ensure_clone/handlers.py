import os
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado


logger = logging.getLogger("jupyterlab_ensure_clone")
logger.setLevel(logging.DEBUG)


class RouteHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        repoUrl = data.get("repoUrl")
        if not repoUrl:
            raise tornado.web.HTTPError(400, "repoUrl is required")
        parsedUrl = urlparse(repoUrl)
        if not all((parsedUrl.scheme, parsedUrl.netloc, parsedUrl.path)):
            raise tornado.web.HTTPError(400, "invalid repoUrl")
        cloneDir = data.get("cloneDir", parsedUrl.path.rsplit("/", 1)[-1]).removesuffix(".git")
        if Path(cloneDir).expanduser().is_dir():
            logger.debug("cloneDir %r exists, assuming repo already cloned there", cloneDir)
            self.set_status(204)
            self.finish()
            return
        username = data.get("username")
        password = data.get("password")
        if username or password:
            repoUrl = f"https://{username}:{password}@{parsedUrl.netloc}{parsedUrl.path}"
        try:
            subprocess.check_call(("git", "clone", repoUrl, cloneDir), env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except subprocess.CalledProcessError:
            logging.error("Failed to clone repo, see output above")
            raise tornado.web.HTTPError(400, reason=f"Failed to clone {repoUrl}, maybe due to bad credentials") from None
        logger.debug("cloned repo into %r", cloneDir)
        self.set_status(204)
        self.finish()


def setup_handlers(web_app):
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]
    route_pattern = url_path_join(base_url, "jupyterlab-ensure-clone")
    handlers = [(route_pattern, RouteHandler)]
    web_app.add_handlers(host_pattern, handlers)