import pathlib, subprocess, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
DOCKER=ROOT/'docker/Dockerfile.general-cafe-builder'
SCRIPT=ROOT/'scripts/run-veci-general-cafe-container.sh'
class ContainerBuildTests(unittest.TestCase):
 def test_shell_parses(self):
  r=subprocess.run(['sh','-n',str(SCRIPT)],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)
 def test_no_router_mutation_and_low_priority_limiter(self):
  s=SCRIPT.read_text()
  for term in ('--cpus=1.5','--memory=4g','--memory-swap=6g',
               '--cap-drop=ALL','--security-opt=no-new-privileges',
               '--user 1000:1000','-v "$repo:/firmware:ro"','/mnt/data/andre-maintenance-archives/',
               'c740570351512e4400369b3c2aff49741f65580e'):
   self.assertIn(term,s)
  for term in ('sysupgrade','scp','ssh root@','apk add','apt-get','--privileged','--network=host'):
   self.assertNotIn(term,s)
 def test_dockerfile_build_only(self):
  s=DOCKER.read_text()
  self.assertIn('ubuntu:24.04@sha256:',s)
  self.assertIn('libncurses-dev',s)
  self.assertIn('USER 1000:1000',s)
  self.assertNotIn('openssh-server',s)
  self.assertNotIn('ENTRYPOINT',s)
if __name__=='__main__':unittest.main()
