#!/usr/bin/python

from subprocess import Popen, PIPE
from modules.git_format import *


class GitError(Exception):
    def __init__(self, value):
        self.value = format_lines(value)

    def __str__(self):
        return repr(self.value)


def execute(command, return_response=False):
    with Popen(command, shell=True, stdout=PIPE, stderr=PIPE) as process:
        try:
            (response, error) = process.communicate()
        except:
            process.kill()
            raise GitError('Fatal: Cannot execute command.')

        if process.poll():
            raise GitError(get_decoded_lines(error))

        if return_response:
            return format_rows(get_decoded_lines(response))


def set_config_options():
    execute('git config --global push.followTags true')
    execute('git config user.name corvus_admin')


def is_inside_work_tree():
    return execute('git rev-parse --is-inside-work-tree', WITH_RESPONSE)


def find_branch(branch_name):
    return execute('git for-each-ref --format="%(refname:short)" refs/heads/' +
                   branch_name + ' refs/remotes/origin/' + branch_name, WITH_RESPONSE)


def squash_all_commits(version):
    commit_sha = execute('git commit-tree HEAD^^{tree} -m "%s"' % version, WITH_RESPONSE)
    execute('git reset %s' % commit_sha)
    stage_all_changes()


def create_new_branch(branch_name, main_branch):
    execute('git branch %s %s' % (branch_name, main_branch))
    checkout(branch_name)


def commit_amend():
    execute('git commit --amend --no-edit')


def get_sha_of_commit_with_msg(branch_name):
    return execute('git log -1 --pretty=%h --grep=' + branch_name, WITH_RESPONSE)


def checkout(branch_name):
    execute('git checkout %s' % branch_name)


def get_current_branch():
    return execute('git symbolic-ref --short HEAD', WITH_RESPONSE)


def verify_head():
    execute('git rev-parse --verify HEAD')


def verify_merge():
    execute('git merge HEAD')


def unstaged_changes():
    return execute('git diff-files --quiet --ignore-submodules', WITH_RESPONSE)


def uncommited_changes():
    return execute('git diff-index --cached --ignore-submodules HEAD --', WITH_RESPONSE)


def update_index():
    execute('git update -index -q --ignore-submodules --refresh')


def add_tag(tag_name):
    execute('git tag -a %s -m "%s"' % (tag_name, tag_name))
    execute('git push origin %s' % tag_name)


def remove_tag(tag_name):
    execute('git tag -d %s' % tag_name)
    execute('git push --delete origin %s' % tag_name)


def check_tag_locally(tag_name):
    execute('git describe --abbrev=0 --match=%s' % tag_name)


def check_tag_remotely(tag_name):
    return execute('git ls-remote --tags origin' % tag_name, WITH_RESPONSE)


def create_patch(starting_tag, ending_tag, patch_name):
    execute('git diff --full-index --binary %s %s > %s' % (starting_tag, ending_tag, patch_name))


def apply_patch(patch_name):
    execute('git apply --check %s' % patch_name)
    execute('git apply -p1 < %s' % patch_name)


def stage_all_changes():
    execute('git add --all')


def commit(message):
    execute('git commit -m "%s"' % message)


def commit_all_changes(commit_msg):
    stage_all_changes()
    commit(commit_msg)


def get_last_commit_msg_with_substring(message):
    return execute("git log -1 --pretty=%B --grep=" + message, WITH_RESPONSE)


def get_last_commit_msg():
    return execute('git log -1 --pretty=%B', WITH_RESPONSE)


def revert_commit(sha='HEAD'):
    execute('git revert --no-commit %s' % sha)


def delete_patch(file_name):
    execute('rm %s' % file_name)


def hard_reset_to_previous_commit():
    execute('git reset --hard HEAD~1')


def push_to_origin(branch_name, upstream=False):
    set_upstream = ''
    if upstream is True:
        set_upstream = '--set-upstream'

    execute('git push -f origin %s %s' % (branch_name, set_upstream))


def fetch_with_status():
    execute('git fetch')
    return execute('git status', WITH_RESPONSE)
