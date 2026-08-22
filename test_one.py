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

import sys, os, types, signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if 'termios' not in sys.modules:
    t=types.ModuleType('termios'); t.error=OSError; t.ICANON=2; t.ECHO=8; t.TCSANOW=0; t.tcgetattr=lambda fd:[0]*7; t.tcsetattr=lambda fd,w,a:None; sys.modules['termios']=t
if 'pwd' not in sys.modules:
    p=types.ModuleType('pwd'); p.getpwnam=lambda u:None; p.getpwuid=lambda u:types.SimpleNamespace(pw_name='root',pw_uid=0,pw_gid=0,pw_dir='/root',pw_shell='/bin/sh'); p.struct_passwd=lambda t:types.SimpleNamespace(pw_name=t[0],pw_uid=t[2],pw_gid=t[3],pw_dir=t[5],pw_shell=t[6]); sys.modules['pwd']=p
if 'spwd' not in sys.modules:
    s=types.ModuleType('spwd'); s.getspnam=lambda u:None; sys.modules['spwd']=s
if 'crypt' not in sys.modules:
    c=types.ModuleType('crypt'); c.crypt=lambda pw,salt:pw; sys.modules['crypt']=c
for a,d in [('SIGHUP',1),('SIGQUIT',3),('SIGUSR1',10),('SIGUSR2',12),('SIGKILL',9),('SIGSTOP',17),('SIGCONT',19),('SIGTERM',15)]:
    if not hasattr(signal,a): setattr(signal,a,d)
for a in ['getuid','getgid','geteuid','getegid']:
    if not hasattr(os,a): setattr(os,a,lambda:0)
name = sys.argv[1] if len(sys.argv)>1 else "boolean_ops"
mod = __import__(f"bin.{name}", fromlist=[name])
result = mod._selftest()
print(f"{name}: {result}")
