from typing import Dict
from kiwi.tasks.system_build import SystemBuildTask

import os
import logging
from itertools import zip_longest

# project
from kiwi.help import Help
from kiwi.system.prepare import SystemPrepare
from kiwi.system.setup import SystemSetup
from kiwi.builder import ImageBuilder
from kiwi.system.profile import Profile
from kiwi.defaults import Defaults
from kiwi.privileges import Privileges
from kiwi.path import Path

log = logging.getLogger('kiwi')



class LocalBuildTask(SystemBuildTask):
    """
    Wrapper Class
    Overloads load_xml_description(...).
    Method is expanded to directly alter the xml state 
    in order to inject the in berrymill.conf defined repositories

    """
    def __init__(self, repos:Dict[str, Dict[str,str]]) -> None:
        super().__init__()
        self.repos:Dict[str, Dict[str,str]] = repos

    
    def load_xml_description(self, description_directory: str, kiwi_file: str = '') -> None:
        super().load_xml_description(description_directory, kiwi_file)

        self.xml_state.delete_repository_sections()
        for reponame in self.repos:

            repodata:Dict[str,str] = self.repos.get(reponame)

            components = repodata.get("components", "/")
            components = components if components != '/' else None
            if components:
                components = components.replace(",", " ")
            distro = repodata.get("name", None)
            print(repodata.get("key"))
            self.xml_state.add_repository(
                repo_source=repodata.get("url"),
                repo_type=repodata.get("type"),
                repo_alias=reponame,
                repo_signing_keys=[repodata.get("key")],
                components=components,
                distribution=distro,
                repo_gpgcheck=False
            )
