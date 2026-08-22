# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import shutil
import logging


def show_license():
    print("UMER OS END USER LICENSE AGREEMENT (EULA)")
    print("This software is provided 'AS IS'. Umer OS team is not liable")
    print("for data loss, hardware damage, or warranty voidance.")
    input("Press ENTER to accept and continue...")


def install_umer_os(target_dir="/umer_os"):
    logging.info("Preparing installation...")
    os.makedirs(target_dir, exist_ok=True)
    for src in ["kernel", "quantum", "ai", "security", "ui", "compatibility", "filesystem", "update", "drivers", "bootloader"]:
        if os.path.exists(src):
            dst = os.path.join(target_dir, src)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
    logging.info("Installation complete. Run: python main.py")


if __name__ == "__main__":
    show_license()
    install_umer_os()