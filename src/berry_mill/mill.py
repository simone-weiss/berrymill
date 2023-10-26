import argparse
import kiwi.logger
import sys
import os
import yaml
from kiwi.exceptions import KiwiPrivilegesError

from .cfgh import ConfigHandler, Autodict
from .localrepos import DebianRepofind
from .sysinfo import get_local_arch
from .preparer import KiwiPreparer
from .builder import KiwiBuilder
from .sysinfo import has_virtualization

log = kiwi.logging.getLogger('kiwi')

no_nested_warning: str = str(
"""
Nested virtualization is NOT enabled. This can cause the build to fail
as a virtual enviroment using qemu is utilized to build the image.

You can either: 

Enable nested virtualization, build locally, or, use --ignore-nested when you are
sure that you are not running berrymill inside a virtual machine
"""
)

class ImageMill:
    """
    ImageMill class
    """

    def __init__(self):
        """
        Constructor
        """
        # Display just help if run alone
        if len(sys.argv) == 1:
            sys.argv.append("--help")

        p:argparse.ArgumentParser = argparse.ArgumentParser(prog="berrymill",
                                                            description="berrymill is a root filesystem generator for embedded devices",
                                                            epilog="Have a lot of fun!")
        
        p.add_argument("-s", "--show-config", action="store_true", help="shows the building configuration")
        p.add_argument("-d", "--debug", action="store_true", help="turns on verbose debugging mode")
        p.add_argument("-a", "--arch", help="specify target arch")
        p.add_argument("-c", "--config", type=str, help="specify configuration other than default")
        p.add_argument("-i", "--image", required=True, help="path to the image appliance, if it is not found in the current directory")
        p.add_argument("-p", "--profile", help="select profile for images that makes use of it")
        p.add_argument("--clean", action="store_true", help="cleanup previous build results prior build.")

        sub_p = p.add_subparsers(help="Course of action for berrymill",dest="subparser_name")
        
        # prepare specific arguments
        prepare_p:argparse.ArgumentParser= sub_p.add_parser("prepare", help="prepare sysroot")
        prepare_p.add_argument("--root", required=True, help="directory of output sysroot")
        prepare_p.add_argument("--allow-existing-root", action="store_true", help="allow existing root")

        # build specific arguments
        build_p:argparse.ArgumentParser = sub_p.add_parser("build", help="build image")
        build_p.add_argument("--box-memory", type=str, default="8G", help="specify main memory to use for the QEMU VM (box)")

        # --cross sets a cpu -> dont allow user to choose cpu when cross is enabled
        build_fashion = build_p.add_mutually_exclusive_group()
        build_fashion.add_argument("--cpu", help="cpu to use for the QEMU VM (box)")
        build_fashion.add_argument("--cross", action="store_true", help="cross image build on x86_64 to aarch64 target")
        build_fashion.add_argument("-l", "--local", action="store_true", help="build image on current hardware")


        build_p.add_argument("--target-dir", required=True, type=str, help="store image results in given dirpath")
        build_p.add_argument("--no-accel", action="store_true", help="disable KVM acceleration for boxbuild")
        build_p.add_argument("--ignore-nested", action="store_true", help="ignore no nested virtualization enabled warning")


        self.args:argparse.Namespace = p.parse_args()

        self.cfg:ConfigHandler = ConfigHandler()
        if self.args.config:
            self.cfg.add_config(self.args.config)
        self.cfg.load()

        # Set appliance paths
        self._appliance_path: str = os.path.dirname(self.args.image or ".")
        if self._appliance_path == ".":
            self._appliance_path = ""

        self._appliance_descr: str = os.path.basename(self.args.image or ".")
        if self._appliance_descr == ".":
            self._appliance_descr = ""
        if not self._appliance_descr:
            for pth in os.listdir(self._appliance_path or "."):
                if pth.split('.')[-1] in ["kiwi", "xml"]:
                    self._appliance_descr = pth
                    break

    def _init_local_repos(self) -> None:
        """
        Initialise local repositories, those are already configured on the local machine.
        """
        if not self.cfg.raw_unsafe_config().get("use-global-repos", False): 
            return

        if self.cfg.raw_unsafe_config()["repos"].get("local") is not None:
            return
        else:
            self.cfg.raw_unsafe_config()["repos"]["local"] = Autodict()

        for r in DebianRepofind().get_repos():
            jr = r.to_json()
            for arch in jr.keys():
                if not self.cfg.raw_unsafe_config()["repos"]["local"].get(arch):
                    self.cfg.raw_unsafe_config()["repos"]["local"][arch] = Autodict()
                self.cfg.raw_unsafe_config()["repos"]["local"][arch].update(jr[arch])
        return

    def run(self) -> None:
        """
        Build an image
        """

        self._init_local_repos()

        if self.args.show_config:
            print(yaml.dump(self.cfg.config))
            return

        if not self._appliance_descr:
            raise Exception("Appliance description was not found.")

        if self._appliance_path:
            os.chdir(self._appliance_path)

        if self.args.subparser_name == "build":
            # parameter "cross" implies a amd64 host and an arm64 target-arch
            if self.args.cross:
                self.args.arch = "arm64"

            if not self.args.local and not self.args.ignore_nested:
                if not has_virtualization():
                    log.info("Berrymill currently cannot detect wether you run it in a virtual environment or on a bare metal")
                    log.warning(no_nested_warning)
                    return
                
            boxed_conf: str|None = self.cfg.raw_unsafe_config().get("boxed_plugin_conf")
            if boxed_conf is not None: 
                os.environ["KIWI_BOXED_PLUGIN_CFG"] = boxed_conf
            else:
                os.environ["KIWI_BOXED_PLUGIN_CFG"] = "/etc/berrymill/kiwi_boxed_plugin.yml"

            kiwip = KiwiBuilder(self._appliance_descr, 
                            box_memory= self.args.box_memory, 
                            profile= self.args.profile, 
                            debug=self.args.debug, 
                            clean= self.args.clean,
                            cross= self.args.cross,
                            cpu= self.args.cpu,
                            local= self.args.local,
                            target_dir= self.args.target_dir,
                            no_accel= self.args.no_accel                          
                            )
        elif self.args.subparser_name == "prepare":           
            kiwip = KiwiPreparer(self._appliance_descr,
                            root=self.args.root,
                            debug=self.args.debug,
                            profile=self.args.profile,
                            allow_existing_root=self.args.allow_existing_root
                            )
        else:
            raise argparse.ArgumentError(argument=None, message="No Action defined (build, prepare)")
         
        for r in self.cfg.config["repos"]:
            for rname, repo in (self.cfg.config["repos"][r].get(self.args.arch or get_local_arch()) or {}).items():
                kiwip.add_repo(rname, repo)

        try:
            kiwip.process()
        finally:
            kiwip.cleanup()


