import os
import pytest
import shutil
from pathlib import Path
from typing import Any, cast

from fora import example_deploys

def test_init_unknown():
    with pytest.raises(ValueError, match="Unknown deploy layout structure"):
        example_deploys.init_deploy_structure(cast(Any, "__unknown"))

def test_init(request, tmp_path):
    try:
        for layout in ["minimal", "flat", "dotfiles", "modular", "staging_prod"]:
            p = os.path.join(tmp_path, layout)
            if os.path.exists(p):
                shutil.rmtree(p)
            Path(p).mkdir(exist_ok=False)

            os.chdir(p)
            with pytest.raises(SystemExit):
                example_deploys.init_deploy_structure(cast(Any, layout))
    finally:
        os.chdir(request.config.invocation_dir)
