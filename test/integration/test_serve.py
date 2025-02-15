import os
import platform
import signal
import subprocess
import time
import unittest

from .. import *
from mike import git_utils


@unittest.skipIf(platform.system() == 'Windows',
                 "SIGINT doesn't work on windows")
class TestServe(unittest.TestCase):
    def setUp(self):
        self.stage = stage_dir('serve')
        git_init()
        copytree(os.path.join(test_data_dir, 'basic_theme'), self.stage)
        check_call_silent(['git', 'add', 'mkdocs.yml', 'docs'])
        check_call_silent(['git', 'commit', '-m', 'initial commit'])

        with git_utils.Commit('gh-pages', 'add file') as commit:
            commit.add_file(git_utils.FileInfo('index.html', 'main page'))
            commit.add_file(git_utils.FileInfo('dir/index.html', 'sub page'))

    def _check_serve(self, options=[], err_output=''):
        env = dict(os.environ)
        env['PYTHONUNBUFFERED'] = '1'
        proc = subprocess.Popen(
            ['mike', 'serve', '--dev-addr=localhost:8888'] + options,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=env
        )

        # Read the first two lines
        stdout_start = proc.stdout.readline() + proc.stdout.readline()
        time.sleep(1)
        proc.send_signal(signal.SIGINT)
        stdout_end, stderr = proc.communicate()

        self.assertEqual(stdout_start,
                         'Starting server at http://localhost:8888/\n' +
                         'Press Ctrl+C to quit.\n')
        self.assertEqual(stdout_end, 'Stopping server...\n')
        self.assertEqual(stderr, err_output)

    def test_serve(self):
        self._check_serve()

    def test_from_subdir(self):
        os.mkdir('sub')
        with pushd('sub'):
            self._check_serve(['-F', '../mkdocs.yml'])
            self._check_serve(['-b', 'gh-pages', '-r', 'origin'])

    def test_local_empty(self):
        origin_rev = git_utils.get_latest_commit('gh-pages')

        stage_dir('serve_clone')
        check_call_silent(['git', 'clone', self.stage, '.'])
        git_config()

        self._check_serve()
        self.assertEqual(git_utils.get_latest_commit('gh-pages'), origin_rev)

    def test_ahead_remote(self):
        origin_rev = git_utils.get_latest_commit('gh-pages')

        stage_dir('serve_clone')
        check_call_silent(['git', 'clone', self.stage, '.'])
        check_call_silent(['git', 'fetch', 'origin', 'gh-pages:gh-pages'])
        git_config()

        with git_utils.Commit('gh-pages', 'add file') as commit:
            commit.add_file(git_utils.FileInfo(
                'file.txt', 'this is some text'
            ))
        clone_rev = git_utils.get_latest_commit('gh-pages')

        self._check_serve()
        self.assertEqual(git_utils.get_latest_commit('gh-pages'), clone_rev)
        self.assertEqual(git_utils.get_latest_commit('gh-pages^'), origin_rev)

    def test_behind_remote(self):
        stage_dir('serve_clone')
        check_call_silent(['git', 'clone', self.stage, '.'])
        check_call_silent(['git', 'fetch', 'origin', 'gh-pages:gh-pages'])
        git_config()

        with pushd(self.stage):
            with git_utils.Commit('gh-pages', 'add file') as commit:
                commit.add_file(git_utils.FileInfo(
                    'file.txt', 'this is some text'
                ))
            origin_rev = git_utils.get_latest_commit('gh-pages')
        check_call_silent(['git', 'fetch', 'origin'])

        self._check_serve()
        self.assertEqual(git_utils.get_latest_commit('gh-pages'), origin_rev)

    def test_diverged_remote(self):
        stage_dir('serve_clone')
        check_call_silent(['git', 'clone', self.stage, '.'])
        check_call_silent(['git', 'fetch', 'origin', 'gh-pages:gh-pages'])
        git_config()

        with pushd(self.stage):
            with git_utils.Commit('gh-pages', 'add file') as commit:
                commit.add_file(git_utils.FileInfo(
                    'file-origin.txt', 'this is some text'
                ))
            origin_rev = git_utils.get_latest_commit('gh-pages')

        with git_utils.Commit('gh-pages', 'add file') as commit:
            commit.add_file(git_utils.FileInfo(
                'file.txt', 'this is some text'
            ))
        clone_rev = git_utils.get_latest_commit('gh-pages')
        check_call_silent(['git', 'fetch', 'origin'])

        self._check_serve(err_output=(
            'warning: gh-pages has diverged from origin/gh-pages\n' +
            '  Pass --ignore to ignore this or --rebase to rebase onto ' +
            'remote\n'
        ))
        self.assertEqual(git_utils.get_latest_commit('gh-pages'), clone_rev)

        self._check_serve(['--ignore'])
        self.assertEqual(git_utils.get_latest_commit('gh-pages'), clone_rev)

        self._check_serve(['--rebase'])
        self.assertEqual(git_utils.get_latest_commit('gh-pages'), origin_rev)
