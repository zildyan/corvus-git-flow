#!/usr/bin/python

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
APPROVAL = 'waiting_for_approval'
OVERALL_APPROVAL = 'waiting_for_overall_approval'


def formatted(string_value):
    return '\n'.join(string_value)


def execute(command, return_response=False):
    git_query = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    (git_response, error) = git_query.communicate()

    if git_query.poll() == 0:
        if return_response is True:
            git_response = git_response.decode()
            return formatted(git_response.splitlines())
        return

    else:
        error = error.decode()
        raise GitError(formatted(error.splitlines()))


def start_flow_initialization(root_branch, version):
    try:
        validate_initialization(root_branch)
        execute('git config --global push.followTags=True')

        for branch in MAIN_BRANCHES:
            create_new_branch(branch, root_branch)

            if branch in [PROD, RELEASE, DEVELOP]:
                squash_all_commits(version)

            commit_amend()

            if branch in [RELEASE, STABLE, HISTORY]:
                add_tag('%s/%s' % (branch, version))

            push_to_origin(branch)

        # git_delete_local_branch(root_branch)

        msg = ('  Flow initialization successfully finished.\n'
               '  Set default branch on remote repository to PROD.')

        return msg

    except GitError as ex:
        raise ex


def validate_initialization(root_branch):
    remote_branches = execute('git branch -r', RETURN_RESPONSE)
    local_branches = execute('git branch', RETURN_RESPONSE)

    if root_branch not in local_branches:
        raise GitError('  Specified root branch does not exists.')

    for branch in MAIN_BRANCHES:
        if branch in remote_branches or branch in local_branches:
            raise GitError('  Corvus git flow main branches already initialized.')


def validate_repository():
    remote_branches = execute('git branch -r', RETURN_RESPONSE)
    local_branches = execute('git branch', RETURN_RESPONSE)

    for branch in MAIN_BRANCHES:
        if branch not in remote_branches and branch not in local_branches:
            raise GitError('  %s branch is not initialized.' % branch)


def validate_branch():
    current_branch = get_current_branch()

    if current_branch in MAIN_BRANCHES or JUNK in current_branch:
        raise GitError('  Command isn\'t allowed on main branches.')

    invalid_branch = True

    for branch in [HOTFIX, BUGFIX, FEATURE]:
        if current_branch.startswith(branch):
            invalid_branch = False
            break

    if invalid_branch is True:
        raise GitError('  Command isn\'t allowed on custom branches.')


def create_new_bugfix_branch(branch_name):
    return create_flow_branch(branch_name, BUGFIX, STABLE)


def create_new_feature_branch(branch_name):
    return create_flow_branch(branch_name, FEATURE, STABLE)


def create_new_hotfix_branch(branch_name):
    return create_flow_branch(branch_name, HOTFIX, PROD)


def create_new_junk_branch(branch_name):
    return create_flow_branch(branch_name, JUNK)


def dev_test():
    current_branch = get_current_branch()

    validate_conditions_for_test(current_branch)
    test_name = get_test_name(current_branch)

    tag_started = get_started_tag(current_branch)
    tag_testing = get_testing_tag(current_branch)
    patch_name = format_patch_name(current_branch, 'test')

    add_tag(tag_testing)
    create_patch(tag_started, tag_testing, patch_name)

    checkout(DEVELOP)
    apply_patch(patch_name)
    delete_patch(patch_name)
    commit_all_changes(test_name)
    push_to_origin(DEVELOP)

    checkout(current_branch)
    return '  %s applied on DEVELOP.' % test_name


def validate_conditions_for_test(branch):
    tag_started = '%s/started' % branch
    if check_tag(tag_started) is False:
        raise GitError("  Branch is missing 'started' tag.")

    if is_testing_in_progress() is True:
        if branch.startswith(HOTFIX):
            prolong_testing_branch()
            checkout(branch)
        else:
            raise GitError('  Testing in progress')


def get_test_name(current_branch):
    test_name = '%s/test#%d' % (current_branch, get_test_number(current_branch))
    return test_name


def prolong():
    current_branch = get_current_branch()
    tag_testing = get_testing_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    tag_released = get_released_tag(current_branch)

    if check_tag(tag_released) is True:
        raise GitError('Branch is already released')

    elif check_tag(tag_finished) is True:
        remove_tag(tag_finished)
        return '  %s successfully prolonged.' % current_branch

    elif check_tag(tag_testing) is True:
        terminate_test(current_branch)
        remove_tag(tag_testing)
        return '  %s successfully prolonged.' % current_branch

    else:
        raise GitError('  Branch is already active.')


def terminate_test(current_branch):
    if current_branch.startswith(HOTFIX) is True:
        end_dev_test('forced_down')
    else:
        end_dev_test('failed')

    checkout(current_branch)


def finish():
    current_branch = get_current_branch()
    tag_testing = get_testing_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    tag_released = get_released_tag(current_branch)

    if check_tag(tag_released) is True:
        raise GitError('  Branch is already released')

    if check_tag(tag_finished) is True:
        raise GitError('  Branch is already finished')

    if check_tag(tag_testing) is True:
        remove_tag(tag_testing)
        end_dev_test('success')

    checkout(current_branch)
    add_tag(tag_finished)
    return '  %s successfully finished.' % current_branch


def release():
    current_branch = get_current_branch()
    tag_started = get_started_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    tag_released = get_released_tag(current_branch)

    if check_tag(tag_released) is True:
        raise GitError('  Branch is already released')

    if check_tag(tag_finished) is False:
        raise GitError('  Branch is not finished')

    if check_tag(APPROVAL) is True:
        raise GitError('  RELEASE branch is waiting for approval')

    if check_tag(OVERALL_APPROVAL) is True:
        raise GitError('  RELEASE branch is waiting for overall approval')

    patch_name = format_patch_name(current_branch, 'release')
    add_tag(tag_finished)
    create_patch(tag_started, tag_finished, patch_name)

    checkout(RELEASE)
    apply_patch(patch_name)
    delete_patch(patch_name)
    commit_all_changes('%s' % current_branch)
    add_tag(APPROVAL)
    push_to_origin(RELEASE)

    checkout(current_branch)
    return '  %s branch released.' % current_branch


def approve():
    success_msg = '  Released branch approved'

    if get_current_branch() != RELEASE:
        raise GitError('  Command approve is allowed only on RELEASE branch')

    if check_tag(APPROVAL) is True:
        remove_tag(APPROVAL, WITH_FORCE)
        return success_msg

    elif check_tag(OVERALL_APPROVAL) is True:
        remove_tag(OVERALL_APPROVAL)
        return success_msg

    else:
        raise GitError('  RELEASE branch is already approved')


def redeem():
    if get_current_branch() != RELEASE:
        raise GitError('  Command redeem is allowed only on RELEASE branch')

    if check_tag(APPROVAL) is not True:
        raise GitError('  There is nothing to redeem on RELEASE branch')

    branch_name = get_last_commit_msg()
    tag_finished = get_finished_tag(branch_name)
    tag_released = get_released_tag(branch_name)

    checkout(branch_name)
    validate_branch()

    remove_tag(tag_finished)
    remove_tag(tag_released)

    checkout(RELEASE)
    remove_tag(APPROVAL)
    hard_reset()
    push_to_origin(RELEASE)
    return '  %s needs to redeem itself.' % branch_name


def remove(branch_name):
    if get_current_branch() != RELEASE:
        raise GitError('  Command remove is allowed only on RELEASE branch')

    if not get_last_commit_msg_with_substring(branch_name):
        raise GitError('  There is no released feature, bugfix or hotfix named %s' % branch_name)

    if check_tag(APPROVAL) is True:
        raise GitError('  RELEASE branch is waiting for approval')

    if check_tag(OVERALL_APPROVAL) is True:
        raise GitError('  RELEASE branch is waiting for overall approval')

    remove_tag(get_finished_tag(branch_name))
    remove_tag(get_released_tag(branch_name))

    commit_sha = execute('git log -1 --grep=%s --pretty=%h' % branch_name, RETURN_RESPONSE)
    revert_commit(commit_sha)
    commit('REMOVED/%s' % branch_name)
    add_tag(OVERALL_APPROVAL)
    push_to_origin(RELEASE)
    return ' %s successfully removed from RELEASE' % branch_name


def publish(version):
    current_branch = get_current_branch()
    if current_branch != RELEASE and current_branch != HOTFIX:
        raise GitError('  Command publish is allowed only on RELEASE and HOTFIX branches')

    if is_testing_in_progress() is True:
        prolong_testing_branch()
        checkout(current_branch)

    tag_started = get_started_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    patch_name = format_patch_name(current_branch, 'release')
    create_patch(tag_started, tag_finished, patch_name)

    checkout(DEVELOP)
    apply_patch(patch_name)
    commit('%s' % version)

    checkout(RELEASE)
    add_tag('RELEASE/%s' % version)

    checkout(PROD)
    apply_patch(patch_name)
    commit('%s' % version)

    # TODO stable
    push_to_origin(DEVELOP)
    push_to_origin(STABLE)
    push_to_origin(PROD)

    return ''


def checkout(branch_name):
    execute('git checkout %s' % branch_name)


def get_current_branch():
    return execute('git rev-parse --abbrev-ref HEAD', RETURN_RESPONSE)


def create_new_branch(branch_name, main_branch):
    execute('git branch %s %s' % (branch_name, main_branch))
    checkout(branch_name)


def push_branch(branch_name):
    execute('git push --set-upstream origin %s' % branch_name)


def delete_local_branch(branch_name):
    execute('git branch -D %s' % branch_name)


def delete_remote_branch(branch_name):
    execute('git push origin --delete %s' % branch_name)


def create_flow_branch(branch_name, branch_type, main_branch=None):
        if main_branch is None:
            if branch_name.startswith(JUNK):
                main_branch = get_current_branch()

        branch_full_name = '%s/%s' % (branch_type, branch_name)
        create_new_branch(branch_full_name, main_branch)
        commit_amend()
        add_tag('%s/started')
        push_to_origin(branch_full_name, '-u')
        return '  Successfully created %s branch' % branch_full_name


def add_tag(tag_name):
    if check_tag(tag_name) is True:
        raise GitError('  Aborted: tag already exists')
    execute('git tag -a %s -m "%s"' % (tag_name, tag_name))


def push_tag(tag_name):
    if check_tag(tag_name) is False:
        raise GitError('  Aborted: tag does not exists')
    execute('git push tag %s' % tag_name)


def check_tag(tag_name):
    tags = execute('git tag', RETURN_RESPONSE)
    if tag_name in tags:
        return True
    return False


def remove_tag(tag_name):
    if check_tag(tag_name):
        execute('git tag -d %s' % tag_name)
        execute('git push --delete origin %s' % tag_name)


def get_started_tag(branch_name):
    return '%s/started' % branch_name


def get_testing_tag(branch_name):
    return '%s/testing' % branch_name


def get_finished_tag(branch_name):
    return '%s/finished' % branch_name


def get_released_tag(branch_name):
    return '%s/released' % branch_name


def end_dev_test(reason):
    checkout(DEVELOP)
    if is_testing_in_progress() is False:
        raise GitError('  There is no tests on DEVELOP')

    revert_commit()
    commit('%s/%s' % (get_last_commit_msg(), reason))
    push_to_origin(DEVELOP)
    return


def prolong_testing_branch():
    checkout(DEVELOP)
    branch_name = get_last_commit_msg().split('/test')[0]
    checkout(branch_name)
    prolong()


def is_testing_in_progress():
    checkout(DEVELOP)
    last_commit_msg = get_last_commit_msg()
    return not check_end_keywords(last_commit_msg)


def get_test_number(branch_name):
    checkout(DEVELOP)
    test = get_last_commit_msg_with_substring(branch_name)
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


def create_patch(starting_tag, ending_tag, patch_name):
    execute('git diff --full-index --binary %s %s > %s' % (starting_tag, ending_tag, patch_name))


def apply_patch(patch_name):
    execute('git apply --check %s' % patch_name)
    execute('git apply -p1 < %s' % patch_name)


def format_patch_name(branch_name, type_of_patch):
    branch = list(branch_name)
    branch[branch.index('/')] = '_'
    return '%s_%s.patch' % (''.join(branch), type_of_patch)


def add_all_to_stage():
    execute('git add --all')


def commit(message):
    execute('git commit -m ' + message)


def commit_all_changes(commit_msg):
    add_all_to_stage()
    commit(commit_msg)


def squash_all_commits(version):
    commit_sha = execute('git commit-tree HEAD^^{tree} -m "%s"' % version, RETURN_RESPONSE)
    execute('git reset %s' % commit_sha)


def get_last_commit_msg_with_substring(message):
    return execute("git log -1 --grep='%s/' --pretty=%B" % message, RETURN_RESPONSE)


def get_last_commit_msg():
    return execute('git log -1 --pretty=%B', RETURN_RESPONSE)


def commit_amend(message=None):
    if message is None:
        execute('git commit --amend --no-edit')
    else:
        execute('git commit --amend -m "%s"' % message)


def revert_commit(sha='head'):
    execute('git revert --no-commit $s' % sha)


def delete_patch(file_name):
    execute('rm %s' % file_name)


def hard_reset(head_num=1):
    execute('git reset --hard head~%s' % head_num)


def soft_reset(file_name):
    execute('git reset %s' % file_name)


def push_to_origin(branch_name, upstream=''):
    execute('git push -f %s origin %s' % (upstream, branch_name))