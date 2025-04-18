# Copyright (c)  2021  Xiaomi Corporation (author: Fangjun Kuang)

import glob
import os
import platform
import shutil
import sys
from pathlib import Path

import setuptools
import torch
from setuptools.command.build_ext import build_ext


def get_pytorch_version():
    # if it is 1.7.1+cuda101, then strip +cuda101
    return torch.__version__.split("+")[0]


def is_for_pypi():
    ans = os.environ.get("KALDIFEAT_IS_FOR_PYPI", None)
    return ans is not None


def is_macos():
    return platform.system() == "Darwin"


def is_windows():
    return platform.system() == "Windows"


try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            _bdist_wheel.finalize_options(self)
            # In this case, the generated wheel has a name in the form
            # kaldifeat-xxx-pyxx-none-any.whl
            if is_for_pypi() and not is_macos():
                self.root_is_pure = True
            else:
                # The generated wheel has a name ending with
                # -linux_x86_64.whl
                self.root_is_pure = False

except ImportError:
    bdist_wheel = None


def cmake_extension(name, *args, **kwargs) -> setuptools.Extension:
    kwargs["language"] = "c++"
    sources = []
    return setuptools.Extension(name, sources, *args, **kwargs)


class BuildExtension(build_ext):
    def build_extension(self, ext: setuptools.extension.Extension):
        # build/temp.linux-x86_64-3.8
        os.makedirs(self.build_temp, exist_ok=True)

        # build/lib.linux-x86_64-3.8
        os.makedirs(self.build_lib, exist_ok=True)

        kaldifeat_dir = Path(__file__).parent.parent.resolve()

        cmake_args = os.environ.get("KALDIFEAT_CMAKE_ARGS", "")
        make_args = os.environ.get("KALDIFEAT_MAKE_ARGS", "")
        system_make_args = os.environ.get("MAKEFLAGS", "")

        if cmake_args == "":
            cmake_args = "-DCMAKE_BUILD_TYPE=Release"

        extra_cmake_args = " -Dkaldifeat_BUILD_TESTS=OFF "
        extra_cmake_args += f" -DCMAKE_INSTALL_PREFIX={Path(self.build_lib).resolve()}/kaldifeat "  # noqa
        # CUDA architecture seperated by ';'
        extra_cmake_args += f' -DCMAKE_CUDA_ARCHITECTURES="80;86;89;90;120" '
        extra_cmake_args += " -DCUDA=ON "

        major, minor = get_pytorch_version().split(".")[:2]
        print("major, minor", major, minor)
        major = int(major)
        minor = int(minor)
        if major > 2 or (major == 2 and minor >= 1):
            extra_cmake_args += f" -DCMAKE_CXX_STANDARD=17 "

        if "PYTHON_EXECUTABLE" not in cmake_args:
            print(f"Setting PYTHON_EXECUTABLE to {sys.executable}")
            cmake_args += f" -DPYTHON_EXECUTABLE={sys.executable}"

        cmake_args += extra_cmake_args

        if is_windows():
            build_cmd = f"""
                cmake {cmake_args} -B {self.build_temp} -S {kaldifeat_dir}
                cmake --build {self.build_temp} --target _kaldifeat --config Release -- -m
                cmake --build {self.build_temp} --target install --config Release -- -m
            """
            print(f"build command is:\n{build_cmd}")
            ret = os.system(
                f"cmake {cmake_args} -B {self.build_temp} -S {kaldifeat_dir}"
            )
            if ret != 0:
                raise Exception("Failed to configure kaldifeat")

            ret = os.system(
                f"cmake --build {self.build_temp} --target _kaldifeat --config Release -- -m"
            )
            if ret != 0:
                raise Exception("Failed to build kaldifeat")

            ret = os.system(
                f"cmake --build {self.build_temp} --target install --config Release -- -m"
            )
            if ret != 0:
                raise Exception("Failed to install kaldifeat")
        else:
            if make_args == "" and system_make_args == "":
                print("For fast compilation, run:")
                print('export KALDIFEAT_MAKE_ARGS="-j"; python setup.py install')
                make_args = " -j4 "
                print("Setting make_args to '-j4'")

            build_cmd = f"""
                mkdir -p {self.build_temp}
                cd {self.build_temp}
                cmake {cmake_args} {kaldifeat_dir}
                make {make_args} _kaldifeat install
            """
            print(f"build command is:\n{build_cmd}")

            ret = os.system(build_cmd)
            if ret != 0:
                raise Exception(
                    "\nBuild kaldifeat failed. Please check the error message.\n"
                    "You can ask for help by creating an issue on GitHub.\n"
                    "\nClick:\n\thttps://github.com/csukuangfj/kaldifeat/issues/new\n"  # noqa
                )
