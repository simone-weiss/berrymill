from typing import Dict, List, Union
from typing_extensions import Unpack
from berry_mill.kiwiapp import KiwiAppPrepare
from berry_mill.kiwrap import KiwiParent
from berry_mill.params import KiwiPrepParams


class KiwiPreparer(KiwiParent):
    """
    Main Class for Berrymill to prepare the "kiwi-ng system prepare" call
    """
    def __init__(self, descr:str, **kw: Unpack[KiwiPrepParams]):
        super().__init__(descr=descr,
                        profile=kw.get("profile"),
                        debug=kw.get("debug"))
        
        self._params:Dict[KiwiPrepParams] = kw
    
    def process(self) -> None:
        """
        Create the arguments for kiwi-ng call and run the Kiwi Prepare Task
        """
        root:str|None = self._params.get("root")

        assert root is not None, "output directory for root folder mandatory"

        command:List[str] = ["kiwi-ng"] + self._kiwi_options + ["system", "prepare"]
        command += ["--description", self._appliance_path]
        command += ["--root", root]

        if "allow_existing_root" in self._params:
            command.append("--allow-existing-root")

        KiwiAppPrepare(command, repos=self._repos).run()

    def cleanup(self) -> None:
        # Nothing to clean up
        super().cleanup()

        if not self._initialized:
            print("Cleanup finished")
            return