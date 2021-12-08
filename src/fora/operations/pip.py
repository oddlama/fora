"""Provides operations related to git."""

import os
from typing import Optional
import fora.host
from fora.operations.api import Operation, OperationResult, operation
from fora.operations.utils import check_absolute_path
