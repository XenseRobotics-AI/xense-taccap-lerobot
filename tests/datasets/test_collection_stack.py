# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""`info.json` must always declare which capture stack produced the dataset.

Downstream merging refuses to mix this recorder's output with datasets converted
from the `TacCap-Collector` backpack stack.  Before this field the only way to
tell them apart was to look for a key one writer happened to emit as a side
effect -- a test is the only thing that keeps the declaration unconditional,
because a missing one causes no error anywhere, just a silently wrong merge.
"""

from lerobot.datasets.utils import COLLECTION_STACK, create_empty_dataset_info


def _info(**kwargs):
    return create_empty_dataset_info(codebase_version="v3.0", fps=30, features={}, use_videos=True, **kwargs)


def test_collection_stack_is_always_present():
    assert _info()["collection_stack"] == COLLECTION_STACK


def test_collection_stack_names_this_repository():
    # The value is a cross-repo contract: TacFlow reads it, and TacCap-Collector
    # writes the other side of it.  "taccap-lerobot" alone is ambiguous -- that
    # is also the name of a crate inside the collector -- so spell out the repo.
    assert COLLECTION_STACK == "xense-taccap-lerobot"


def test_collection_stack_does_not_depend_on_robot_type():
    for robot_type in (None, "bi_taccap_gripper", "xtac_umi_g1"):
        assert _info(robot_type=robot_type)["collection_stack"] == COLLECTION_STACK


def test_collection_stack_sits_next_to_robot_type():
    keys = list(_info(robot_type="bi_taccap_gripper"))
    assert keys.index("collection_stack") == keys.index("robot_type") + 1
