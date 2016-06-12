#!/usr/bin/python

from sys import exit, argv
from subprocess import Popen, PIPE


class GitError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


RETURN_RESPONSE = True
WITH_FORCE = True
HOTFIX = 'HOTFIX'
BUGFIX = 'BUGFIX'
FEATURE = 'FEATURE'
JUNK = 'JUNK'
PROD = 'PROD'
RELEASE = 'RELEASE'
DEVELOP = 'DEVELOP'
STABLE = 'STABLE'
HISTORY = 'HISTORY'
MAIN_BRANCHES = [PROD, RELEASE, DEVELOP, STABLE, HISTORY]
DEVELOP_END_KEYWORDS = ['success', 'failed', 'forced_down']
WAITING_FOR_APPROVAL = 'waiting_for_approval'
WAITING_FOR_OVERALL_APPROVAL = 'waiting_for_overall_approval'


def formatted(string_value):
    return '\n'.join(string_value)


def execute(command, return_response=False):
    git_query = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    (git_response, error) = git_query.communicate()

    if git_query.poll() == 0:
        if return_response is False:
            return
        elif return_response is True:
            git_response = git_response.decode()
            return formatted(git_response.splitlines())
        else:
            raise GitError('Unexisting execute option')
    else:
        error = error.decode()
        raise GitError(formatted(error.splitlines()))


def git_initialization(root_branch, version):
    try:
        if git_repository_prepared(root_branch) is not True:
            return 'Aborted: repository contains branches other than master'

        execute('git config --global push.followTags=True')

        for branch in MAIN_BRANCHES:
            git_new_branch(branch, root_branch)
            git_checkout(branch)

            if branch in [PROD, RELEASE, DEVELOP]:
                git_squash_all_commits(version)

            git_commit_amend()

            if branch in [RELEASE, STABLE, HISTORY]:
                git_add_tag('%s/%s' % (branch, version))

            git_push_origin(branch)

        git_delete_local_branch(root_branch)

        msg = ('Flow initialization successfully finished\n'
               'Set default branch on remote repository to PROD')

        return msg

    except GitError as ex:
        raise ex


def git_repository_prepared(root_branch):
    try:
        remote_branches = execute('git branch -r', RETURN_RESPONSE)
        local_branches = execute('git branch', RETURN_RESPONSE)

        if root_branch not in local_branches:
            return False

        for branch in MAIN_BRANCHES:
            if branch in remote_branches or branch in local_branches:
                return False

        return True

    except GitError as ex:
        raise ex


def git_new_bugfix(branch_name):
    git_make_branch(branch_name, BUGFIX, STABLE)


def git_new_feature(branch_name):
    git_make_branch(branch_name, FEATURE, STABLE)


def git_new_hotfix(branch_name):
    git_make_branch(branch_name, HOTFIX, PROD)


def git_new_junk(branch_name):
    git_make_branch(branch_name, JUNK)


def git_dev_test():
    current_branch = git_current_branch();
    validate_branch(current_branch)

    do_testing = proceed_to_dev_test()

    if do_testing is not True and current_branch == HOTFIX:
        git_checkout(DEVELOP)
        branch_name = git_last_commit_msg().split('/test')[0]
        git_checkout(branch_name)
        git_prolong(WITH_FORCE)

    elif do_testing is not True:
        raise GitError('Testing in progress')

    test_num = git_test_number()
    git_checkout(current_branch)

    tag_started = '%s/started' % current_branch
    if git_check_tag(tag_started) is not True:
        raise GitError("Branch is missing 'started' tag.")

    tag_testing = '%s/testing' % current_branch
    patch_name = format_patch_name(current_branch, 'test')

    git_add_tag(tag_testing)
    git_make_patch(tag_started, tag_testing, patch_name)
    git_checkout(STABLE)
    git_apply_patch(patch_name)
    git_delete_file(patch_name)
    git_add_all()
    git_commit('%s/test#%d' % (current_branch, test_num))
    git_push_origin(STABLE)


def git_prolong(force=False):
    current_branch = git_current_branch()
    validate_branch(current_branch)

    tag_testing = '%s/testing' % current_branch
    tag_finished = '%s/finished' % current_branch
    tag_released = '%s/released' % current_branch

    if git_check_tag(tag_released) is True:
        raise GitError('Branch is already released')

    if git_check_tag(tag_finished) is True:
        git_remove_tag(tag_finished, WITH_FORCE)
        return

    if git_check_tag(tag_testing) is True:
        git_remove_tag(tag_testing, WITH_FORCE)
        if force is True:
            git_end_dev_test('forced_down')
        else:
            git_end_dev_test('failed')
        return

    raise GitError('Branch is already active')


def git_finish():
    current_branch = git_current_branch()
    validate_branch(current_branch)

    tag_testing = '%s/testing' % current_branch
    tag_finished = '%s/finished' % current_branch
    tag_released = '%s/released' % current_branch

    if git_check_tag(tag_released) is True:
        raise GitError('Branch is already released')

    if git_check_tag(tag_finished) is True:
        raise GitError('Branch is already finished')

    if git_check_tag(tag_testing) is True:
        git_remove_tag(tag_testing, WITH_FORCE)
        git_end_dev_test('success')

    git_checkout(current_branch)
    git_add_tag(tag_finished)


def git_release():
    current_branch = git_current_branch()
    validate_branch(current_branch)

    tag_started = '%s/started' % current_branch
    tag_finished = '%s/finished' % current_branch
    tag_released = '%s/released' % current_branch

    if git_check_tag(tag_released) is True:
        raise GitError('Branch is already released')

    if git_check_tag(tag_finished) is False:
        raise GitError('Branch is not finished')

    if git_check_tag(WAITING_FOR_APPROVAL) is True:
        raise GitError('RELEASE branch is waiting for approval')

    if git_check_tag(WAITING_FOR_OVERALL_APPROVAL) is True:
        raise GitError('RELEASE branch is waiting for overall approval')

    patch_name = format_patch_name(current_branch, 'release')

    git_add_tag(tag_finished)
    git_make_patch(tag_started, tag_finished, patch_name)
    git_checkout(RELEASE)
    git_apply_patch(patch_name)
    git_delete_file(patch_name)
    git_add_all()
    git_commit('%s' % current_branch)
    git_add_tag(WAITING_FOR_APPROVAL)
    git_push_origin(RELEASE)


def git_approve():
    if git_current_branch() != RELEASE:
        raise GitError('Command approve is allowed only on RELEASE branch')

    if git_check_tag(WAITING_FOR_APPROVAL) is True:
        git_remove_tag(WAITING_FOR_APPROVAL, WITH_FORCE)
        return

    if git_check_tag(WAITING_FOR_OVERALL_APPROVAL) is True:
        git_remove_tag(WAITING_FOR_OVERALL_APPROVAL)
        return

    raise GitError('RELEASE branch is already approved')


def git_redeem():
    if git_current_branch() != RELEASE:
        raise GitError('Command approve is allowed only on RELEASE branch')

    if git_check_tag(WAITING_FOR_APPROVAL) is not True:
        raise GitError('There is nothing to redeem on RELEASE branch')

    branch_name = git_last_commit_msg()
    tag_finished = '%s/finished' % branch_name
    tag_released = '%s/released' % branch_name
    git_remove_tag(tag_finished)
    git_remove_tag(tag_released)
    git_remove_tag(WAITING_FOR_APPROVAL)
    git_reset_hard()
    git_push_origin(RELEASE)


def git_remove(branch_name):
    if git_current_branch() != RELEASE:
        raise GitError('Command remove is allowed only on RELEASE branch')

    if not git_commit_grep(branch_name):
        raise GitError('There is no released feature, bugfix or hotfix named %s' % branch_name)

    if git_check_tag(WAITING_FOR_APPROVAL) is True:
        raise GitError('RELEASE branch is waiting for approval')

    if git_check_tag(WAITING_FOR_OVERALL_APPROVAL) is True:
        raise GitError('RELEASE branch is waiting for overall approval')

    tag_finished = '%s/finished' % branch_name
    tag_released = '%s/released' % branch_name
    git_remove_tag(tag_finished)
    git_remove_tag(tag_released)

    commit_sha = execute('git log -1 --grep=%s --pretty=%h' % branch_name, RETURN_RESPONSE)
    git_revert_commit(commit_sha)
    git_commit('REMOVED/%s' % branch_name)
    git_add_tag(WAITING_FOR_OVERALL_APPROVAL)
    git_push_origin(RELEASE)


def git_publish(version):
    current_branch = git_current_branch()
    if current_branch != RELEASE and current_branch != HOTFIX:
        raise GitError('Command publish is allowed only on RELEASE and HOTFIX branches')

    if proceed_to_dev_test() is not True:
        git_checkout(DEVELOP)
        branch_name = git_last_commit_msg().split('/test')[0]
        git_checkout(branch_name)
        git_prolong(WITH_FORCE)

    git_checkout(current_branch)
    if current_branch == HOTFIX:
        tag_started = '%s/started' % current_branch
        tag_finished = '%s/finished' % current_branch
        # TODO: dovrsiti


def validate_branch(branch_name):
    invalid_branch = True;

    if branch_name in MAIN_BRANCHES or JUNK in branch_name:
        raise GitError('Command isn\'t allowed on main branches.')

    for branch in [HOTFIX, BUGFIX, FEATURE]:
        if branch_name.startswith(branch):
            invalid_branch = False
            break;

    if invalid_branch is True:
        raise GitError('Command isn\'t allowed on custom branches.')


def git_add_tag(tag_name):
    if git_check_tag(tag_name) is True:
        raise GitError('Aborted: tag already exists')
    execute('git tag -a %s -m "%s"' % (tag_name, tag_name))


def git_push_tag(tag_name):
    if git_check_tag(tag_name) is False:
        raise GitError('Aborted: tag doesn\'t exists')
    execute('git push tag %s' % tag_name)


def git_check_tag(tag_name):
    tags = execute('git tag', RETURN_RESPONSE)
    if tag_name in tags:
        return True
    return False


def git_remove_tag(tag_name, force=False):
    if force is True or git_check_tag(tag_name):
        execute('git tag -d %s' % tag_name)
        execute('git push --delete origin %s' % tag_name)


def git_checkout(branch_name):
    execute('git checkout ' + branch_name)


def git_current_branch():
    return execute('git rev-parse --abbrev-ref HEAD', RETURN_RESPONSE)


def git_new_branch(branch_name, main_branch):
    execute('git branch %s %s' % (branch_name, main_branch))


def git_push_branch(branch_name):
    execute('git push --set-upstream origin %s' % branch_name)


def git_delete_local_branch(branch_name):
    execute('git branch -D %s' % branch_name)


def git_delete_remote_branch(branch_name):
    execute('git push origin --delete %s' % branch_name)


def git_make_branch(branch_name, branch_type, main_branch=None):
    try:
        current_branch = git_current_branch()
        if main_branch is None:
            if branch_name.startswith(JUNK):
                main_branch = current_branch

        branch_full_name = '%s/%s' % (branch_type, branch_name)
        git_new_branch(branch_full_name, main_branch)
        git_checkout(branch_full_name)
        git_commit_amend()
        git_add_tag('%s/started')
        git_push_origin(branch_full_name, '-u')

        return 'Successfully created %s branch' % branch_full_name

    except GitError:
        raise


def git_end_dev_test(reason):
    git_checkout(DEVELOP)
    if proceed_to_dev_test() is not True:
        raise GitError('There is no tests on DEVELOP')

    git_revert_commit()
    git_commit('%s/%s' % (git_last_commit_msg(), reason))
    git_push_origin(DEVELOP)
    return


def proceed_to_dev_test():
    git_checkout(DEVELOP)
    last_commit_msg = git_last_commit_msg()
    return check_end_keywords(last_commit_msg)


def git_test_number(branch_name):
    git_checkout(DEVELOP)
    test = git_commit_grep(branch_name)
    if not test:
        return 1

    test_num = test.split('#')[1]
    if check_end_keywords(test_num) is True:
        test_num = test_num.split('/')[0]

    return int(test_num)


def check_end_keywords(commit_message):
    for word in DEVELOP_END_KEYWORDS:
        if word in commit_message:
            return True
    return False


def git_make_patch(starting_tag, ending_tag, patch_name):
    execute('git diff --full-index --binary %s %s > %s' % (starting_tag, ending_tag, patch_name))


def git_apply_patch(patch_name):
    execute('git apply --check %s' % patch_name)
    execute('git apply -p1 < %s' % patch_name)


def format_patch_name(branch_name, type_of_patch):
    branch = list(branch_name)
    branch[branch.index('/')] = '_'
    return '%s_%s.patch' % (''.join(branch), type_of_patch)


def git_add_all():
    execute('git add --all')


def git_commit(message):
    execute('git commit -m ' + message)


def git_squash_all_commits(version):
    commit_sha = execute('git commit-tree HEAD^^{tree} -m "%s"' % version, RETURN_RESPONSE)
    execute('git reset %s' % commit_sha)


def git_commit_grep(message):
    return execute("git log -1 --grep='%s/' --pretty=%B" % message, RETURN_RESPONSE)


def git_last_commit_msg():
    return execute('git log -1 --pretty=%B', RETURN_RESPONSE)


def git_commit_amend(message=None):
    if message is None:
        execute('git commit --amend --no-edit')
    else:
        execute('git commit --amend -m "%s"' % message)


def git_revert_commit(sha='head'):
    execute('git revert --no-commit $s' % sha)


def git_delete_file(file_name):
    execute('rm %s' % file_name)


def git_reset_hard(head_num=1):
    execute('git reset --hard head~%s' % head_num)


def git_reset(file_name):
    execute('git reset %s' % file_name)


def git_push():
    execute('git push')


def git_push_origin(branch_name, upstream=''):
    execute('git push -f %s origin %s' % (upstream, branch_name))


def git_status():
    return execute('git status', RETURN_RESPONSE)


def main():
    try:
        if 'DEVELOP' in MAIN_BRANCHES:
            print(DEVELOP)

    except GitError as gErr:
        print(gErr.value)


if __name__ == '__main__':
    exit(main())
