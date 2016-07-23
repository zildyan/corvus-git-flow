#!/usr/bin/python

from subprocess import Popen, PIPE


WITH_RESPONSE = True
WITH_FORCE = True
SET_UPSTREAM = True
CHECK_IF_EXISTS = True
HOTFIX = 'HOTFIX'
BUGFIX = 'BUGFIX'
FEATURE = 'FEATURE'
JUNK = 'JUNK'
PROD = 'PROD'
RELEASE = 'RELEASE'
DEVELOP = 'DEVELOP'
STABLE = 'STABLE'
HISTORY = 'HISTORY'
MAIN_BRANCHES = [PROD, RELEASE, STABLE, DEVELOP, HISTORY]
DEVELOP_END_KEYWORDS = ['success', 'failed', 'forced_down']
APPROVAL = 'need_approval'
ALL_APPROVAL = 'need_overall_approval'


class GitError(Exception):
    def __init__(self, value):
        self.value = format_blanks(value)

    def __str__(self):
        return repr(self.value)


def execute(command, return_response=False):
    git_query = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    (response, error) = git_query.communicate()

    if git_query.poll() == 0:
        if return_response is True:
            return format_rows(get_decoded_lines(response))
    else:
        raise GitError(format_lines(get_decoded_lines(error)))


def get_decoded_lines(output):
    return output.decode().splitlines()


def format_lines(lines):
    if len(lines) > 1:
        formatted_lines = []
        for line in lines:
            formatted_lines.append(format_blanks(line))
        return format_rows(formatted_lines)

    else:
        return lines[0]


def format_rows(formatted_lines):
    return '\n'.join(formatted_lines)


def format_blanks(string_value):
    return '  %s' % string_value


def start_flow_initialization(version):
    try:
        validate_initialization()
        root_branch = get_current_branch()
        config_option_push_with_tags()

        for branch in MAIN_BRANCHES:
            create_new_branch(branch, root_branch)

            if branch in [PROD, RELEASE, DEVELOP]:
                squash_all_commits('Flow initialization - version %s - success' % version)

            commit_amend()

            if branch in [RELEASE, STABLE, HISTORY]:
                add_tag('%s/%s' % (branch, version))

            push_to_origin(branch, SET_UPSTREAM)
            checkout(root_branch)

        # delete_local_branch(root_branch)
        msg = ['', 'Flow initialization successfully finished.',
               '', 'Set default branch on remote repository to PROD,',
               'and then manually delete %s' % root_branch]

        return format_lines(msg)

    except GitError as ex:
        raise ex


def validate_initialization():
    validate_directory_is_git_repository()
    validate_main_branches(False)


def validate_directory_is_git_repository():
    response = execute('git rev-parse --is-inside-work-tree', WITH_RESPONSE)
    if 'true' not in response:
        raise GitError('Not a git repository.')


def validate_flow_initialized():
    validate_main_branches(True)


def validate_main_branches(need_to_exists):
    remote_branches = execute('git branch -r', WITH_RESPONSE)
    local_branches = execute('git branch', WITH_RESPONSE)
    all_branches = remote_branches + local_branches

    for branch in MAIN_BRANCHES:
        branch_existence = does_branch_exists(branch, all_branches)

        if branch_existence is True and need_to_exists is False:
            raise GitError('Abort: %s branch already initialized.' % branch)

        if branch_existence is True and exists_locally_and_on_remote(branch, all_branches) is False:
            raise GitError('Abort: %s branch do not exist locally and on remote.' % branch)

        if branch_existence is False and need_to_exists is True:
            raise GitError('Abort: %s branch do not exist.' % branch)


def does_branch_exists(branch, branches):
    if branch in branches:
        return True
    return False


def exists_locally_and_on_remote(branch, branches):
    return branches.count(branch) == 2


def config_option_push_with_tags():
    execute('git config --global push.followTags true')


def squash_all_commits(version):
    commit_sha = execute('git commit-tree HEAD^^{tree} -m "%s"' % version, WITH_RESPONSE)
    execute('git reset %s' % commit_sha)
    stage_all_changes()


def create_new_bugfix_branch(branch_name):
    return create_flow_branch(branch_name, BUGFIX, STABLE)


def create_new_feature_branch(branch_name):
    return create_flow_branch(branch_name, FEATURE, STABLE)


def create_new_hotfix_branch(branch_name):
    return create_flow_branch(branch_name, HOTFIX, PROD)


def create_new_junk_branch(branch_name):
    return create_flow_branch(branch_name, JUNK)


def create_flow_branch(branch_name, branch_type, main_branch=None):
    if main_branch is None:
        if branch_name.startswith(JUNK):
            main_branch = get_current_branch()

    branch_full_name = '%s/%s' % (branch_type, branch_name)
    create_new_branch(branch_full_name, main_branch)
    commit_amend()
    add_tag(get_started_tag(branch_name))
    push_to_origin(branch_full_name, SET_UPSTREAM)
    return format_blanks('Successfully created %s branch' % branch_full_name)


def create_new_branch(branch_name, main_branch):
    execute('git branch %s %s' % (branch_name, main_branch))
    checkout(branch_name)


def commit_amend():
    execute('git commit --amend --no-edit')


def dev_test():
    current_branch = get_current_branch()
    validate_dev_test(current_branch)

    test_name = get_test_name(current_branch)
    tag_started = get_started_tag(current_branch)
    tag_testing = get_testing_tag(current_branch)

    checkout(current_branch)
    add_tag(tag_testing)

    patch_name = format_patch_name(current_branch, 'test')
    create_patch(tag_started, tag_testing, patch_name)

    checkout(DEVELOP)
    apply_patch(patch_name)
    delete_patch(patch_name)
    commit_all_changes(test_name)
    push_to_origin(DEVELOP)

    checkout(current_branch)
    return format_blanks('Test applied on DEVELOP.')


def validate_dev_test(branch_name):
    if not tag_exists(get_started_tag(branch_name)):
        raise GitError("Abort: Branch is missing 'started' tag.")

    if not synchronised_with_remote:
        raise GitError('Abort: Local branch is not synchronised with remote.')

    if is_testing_in_progress() is True:
        if branch_name.startswith(HOTFIX):
            prolong_testing_branch()
        else:
            checkout(branch_name)
            raise GitError('Abort: Test in progress')


def synchronised_with_remote():
    execute('git fetch')
    response = execute('git status', WITH_RESPONSE)
    if 'up-to-date' not in response:
        return False

    return True


def is_testing_in_progress():
    checkout(DEVELOP)
    last_commit_msg = get_last_commit_msg()
    return not check_end_keywords(last_commit_msg)


def prolong_testing_branch():
    checkout(DEVELOP)
    branch_name = get_last_commit_msg().split('/test')[0]
    checkout(branch_name)
    validate_branch()
    prolong()


def get_test_name(branch_name):
    number = get_test_number(branch_name)
    test_name = '%s/test#%s' % (branch_name, str(number))
    return test_name


def get_test_number(branch_name):
    checkout(DEVELOP)
    test = get_last_commit_msg_with_substring(branch_name)
    if test == '':
        return '1'

    test_num = test.split('#')[1]
    if check_end_keywords(test_num) is True:
        test_num = test_num.split('/')[0]

    return int(test_num) + 1


def check_end_keywords(commit_message):
    for word in DEVELOP_END_KEYWORDS:
        if word in commit_message:
            return True

    return False


def prolong():
    current_branch = get_current_branch()
    tag_testing = get_testing_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    tag_released = get_released_tag(current_branch)

    validate_prolong(tag_testing, tag_finished, tag_released)

    if tag_exists(tag_finished):
        remove_tag(tag_finished)

    elif tag_exists(tag_testing):
        terminate_test(current_branch)
        remove_tag(tag_testing)

    return format_blanks('Branch successfully prolonged.')


def validate_prolong(tag_testing, tag_finished, tag_released):
    if tag_exists(tag_released):
        raise GitError('Abort: Branch is already released')

    if tag_exists(tag_testing) is False and tag_exists(tag_finished) is False:
        raise GitError('Abort: Branch is already active.')


def terminate_test(branch_name):
    if branch_name.startswith(HOTFIX):
        end_dev_test('forced_down')
    else:
        end_dev_test('failed')

    checkout(branch_name)


def end_dev_test(reason):
    checkout(DEVELOP)
    if is_testing_in_progress() is False:
        raise GitError('Abort: There is no tests on DEVELOP')

    last_commit_msg = get_last_commit_msg().rstrip()
    commit_msg = '%s/%s' % (last_commit_msg, reason)
    revert_commit()
    commit_all_changes(commit_msg)
    push_to_origin(DEVELOP)


def finish():
    current_branch = get_current_branch()
    tag_testing = get_testing_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    tag_released = get_released_tag(current_branch)

    validate_finish(tag_finished, tag_released)
    finish_test(tag_testing)
    checkout(current_branch)
    add_tag(tag_finished)
    return format_blanks('%s successfully finished.' % current_branch)


def validate_finish(tag_finished, tag_released):
    if tag_exists(tag_released):
        raise GitError('Abort: Branch is already released')
    if tag_exists(tag_finished):
        raise GitError('Abort: Branch is already finished')


def finish_test(tag_testing):
    if tag_exists(tag_testing):
        remove_tag(tag_testing)
        end_dev_test('success')


def release():
    current_branch = get_current_branch()
    tag_started = get_started_tag(current_branch)
    tag_finished = get_finished_tag(current_branch)
    tag_released = get_released_tag(current_branch)

    validate_release(tag_finished, tag_released)

    add_tag(tag_released)
    patch_name = format_patch_name(current_branch, 'release')
    create_patch(tag_started, tag_finished, patch_name)

    checkout(RELEASE)
    apply_patch(patch_name)
    delete_patch(patch_name)

    commit_all_changes('%s' % current_branch)
    add_tag(APPROVAL)
    push_to_origin(RELEASE)
    checkout(current_branch)
    return format_blanks('%s branch released.' % current_branch)


def validate_release(tag_finished, tag_released):
    if tag_exists(tag_released):
        raise GitError('Abort: Branch is already released')
    if not tag_exists(tag_finished):
        raise GitError('Abort: Branch is not finished')
    if tag_exists(APPROVAL):
        raise GitError('Abort: RELEASE branch is waiting for approval')
    if tag_exists(ALL_APPROVAL):
        raise GitError('Abort: RELEASE branch is waiting for overall approval')


def approve():
    validate_approve()

    if tag_exists(APPROVAL):
        remove_tag(APPROVAL)

    elif tag_exists(ALL_APPROVAL):
        remove_tag(ALL_APPROVAL)

    return format_blanks('Successfully approved.')


def validate_approve():
    if get_current_branch() != RELEASE:
        raise GitError('Abort: Command approve is allowed only on RELEASE branch')

    if tag_exists(APPROVAL) is False and tag_exists(ALL_APPROVAL) is False:
        raise GitError('Abort: RELEASE branch is already approved')


def redeem():
    validate_redeem()
    branch_name = get_last_commit_msg()
    checkout(branch_name)
    validate_branch()

    remove_tag(get_finished_tag(branch_name), CHECK_IF_EXISTS)
    remove_tag(get_released_tag(branch_name), CHECK_IF_EXISTS)

    checkout(RELEASE)
    remove_tag(APPROVAL)
    hard_reset_to_previous_commit()
    push_to_origin(RELEASE)
    return format_blanks('%s needs to redeem itself.' % branch_name)


def validate_redeem():
    if get_current_branch() != RELEASE:
        raise GitError('Abort: Command redeem is allowed only on RELEASE branch')
    if tag_exists(APPROVAL):
        raise GitError('Abort: There is nothing to redeem on RELEASE branch')


def validate_branch():
    current_branch = get_current_branch()

    if current_branch in MAIN_BRANCHES or JUNK in current_branch:
        raise GitError('Abort: Command isn\'t allowed on main branches.')

    valid_branch = False

    for branch in [HOTFIX, BUGFIX, FEATURE]:
        if current_branch.startswith(branch):
            valid_branch = True
            break

    if not valid_branch:
        raise GitError('Abort: Command isn\'t allowed on custom branches.')


def remove(branch_name):
    validate_remove(branch_name)
    remove_tag(get_finished_tag(branch_name), CHECK_IF_EXISTS)
    remove_tag(get_released_tag(branch_name), CHECK_IF_EXISTS)

    commit_sha = get_sha_of_commit_with_msg(branch_name)
    revert_commit(commit_sha)
    commit('REMOVED/%s' % branch_name)
    add_tag(ALL_APPROVAL)
    push_to_origin(RELEASE)
    return format_blanks('%s successfully removed from RELEASE' % branch_name)


def validate_remove(branch_name):
    if get_current_branch() != RELEASE:
        raise GitError('Abort: Command remove is allowed only on RELEASE branch')

    if not get_last_commit_msg_with_substring(branch_name):
        raise GitError('Abort: There is no released feature, bugfix or hotfix named %s' % branch_name)

    if tag_exists(APPROVAL):
        raise GitError('Abort: RELEASE branch is waiting for approval')

    if tag_exists(ALL_APPROVAL):
        raise GitError('Abort: RELEASE branch is waiting for overall approval')


def get_sha_of_commit_with_msg(branch_name):
    return execute('git log -1 --grep=%s --pretty=%h' % branch_name, WITH_RESPONSE)


def publish(version):
    current_branch = get_current_branch()
    validate_publish(current_branch)

    if is_testing_in_progress():
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


def validate_publish(current_branch):
    if current_branch != RELEASE and current_branch != HOTFIX:
        raise GitError('Abort: Command publish is allowed only on RELEASE and HOTFIX branches')


def delete_local_branch(branch_name):
    execute('git branch -D %s' % branch_name)


def checkout(branch_name):
    execute('git checkout %s' % branch_name)


def get_current_branch():
    return execute('git rev-parse --abbrev-ref HEAD', WITH_RESPONSE)


def push_branch(branch_name):
    execute('git push --set-upstream origin %s' % branch_name)


def delete_remote_branch(branch_name):
    execute('git push origin --delete %s' % branch_name)


def add_tag(tag_name):
    if tag_exists(tag_name):
        raise GitError('Abort: tag already exists')
    execute('git tag -a %s -m "%s"' % (tag_name, tag_name))


def push_tag(tag_name):
    if not tag_exists(tag_name):
        raise GitError('Abort: Tag does not exists')
    execute('git push tag %s' % tag_name)


def tag_exists(tag_name):
    tags = execute('git tag', WITH_RESPONSE)
    if tag_name in tags:
        return True
    return False


def remove_tag(tag_name, check=False):
    if check is False or tag_exists(tag_name):
        execute('git tag -d %s' % tag_name)
        execute('git push --delete origin %s' % tag_name)
    else:
        raise GitError('%s tag do not exist.')


def get_started_tag(branch_name):
    branch_name = get_branch_identifier_name(branch_name)
    return '%s/started' % branch_name


def get_testing_tag(branch_name):
    branch_name = get_branch_identifier_name(branch_name)
    return '%s/testing' % branch_name


def get_finished_tag(branch_name):
    branch_name = get_branch_identifier_name(branch_name)
    return '%s/finished' % branch_name


def get_released_tag(branch_name):
    branch_name = get_branch_identifier_name(branch_name)
    return '%s/released' % branch_name


def get_branch_identifier_name(branch_name):
    if '/' in branch_name:
        branch_name = branch_name.split('/')[1]
    return branch_name


def create_patch(starting_tag, ending_tag, patch_name):
    execute('git diff --full-index --binary %s %s > %s' % (starting_tag, ending_tag, patch_name))


def apply_patch(patch_name):
    execute('git apply --check %s' % patch_name)
    execute('git apply -p1 < %s' % patch_name)


def format_patch_name(branch_name, type_of_patch):
    branch = list(branch_name)
    branch[branch.index('/')] = '_'
    return '%s_%s.patch' % (''.join(branch), type_of_patch)


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


def revert_commit(sha='head'):
    execute('git revert --no-commit %s' % sha)


def delete_patch(file_name):
    execute('rm %s' % file_name)


def hard_reset_to_previous_commit(head_num=1):
    execute('git reset --hard head~%s' % head_num)


def push_to_origin(branch_name, upstream=False):
    set_upstream = ''
    if upstream is True:
        set_upstream = '--set-upstream'

    execute('git push -f origin %s %s' % (branch_name, set_upstream))


def reset_initialization():
    checkout('master')
    try:
        execute('git branch -D PROD RELEASE DEVELOP STABLE HISTORY')
    except GitError:
        pass
    try:
        execute('git push --delete origin PROD RELEASE DEVELOP STABLE HISTORY')
    except GitError:
        pass
    try:
        execute('git tag -d HISTORY/1.0.0 RELEASE/1.0.0 STABLE/1.0.0')
    except GitError:
        pass
    try:
        execute('git push --delete origin HISTORY/1.0.0 RELEASE/1.0.0 STABLE/1.0.0')
    except GitError:
        pass
    finally:
        execute('git reset --hard origin/master')
        return '  Successfully reset repo.'
