#!/usr/bin/python

WITH_RESPONSE = True
SET_UPSTREAM = True
HOTFIX = 'HOTFIX'
BUGFIX = 'BUGFIX'
FEATURE = 'FEATURE'
SUPPORT = 'SUPPORT'
PROD = 'PROD'
RELEASE = 'RELEASE'
DEVELOP = 'DEVELOP'
STABLE = 'STABLE'
HISTORY = 'HISTORY'
MAIN_BRANCHES = [PROD, RELEASE, STABLE, DEVELOP, HISTORY]
DEVELOP_END_KEYWORDS = ['success', 'failed', 'forced_down']


def get_decoded_lines(output):
    return output.decode().splitlines()


def format_lines(lines):
    if isinstance(lines, list):
        formatted_lines = []
        for line in lines:
            line = str(line).strip()
            if line != '':
                formatted_lines.append(format_blanks(line))
        return format_rows(formatted_lines)

    return format_blanks(lines)


def format_rows(formatted_lines):
    return '\n'.join(formatted_lines)


def format_blanks(string_value):
    blanks = '  '
    return blanks + string_value


def format_patch_name(branch_name, type_of_patch):
    branch = list(branch_name)
    branch[branch.index('/')] = '_'
    return '%s_%s.patch' % (''.join(branch), type_of_patch)


def format_commit_msg(branch_name, commit_msg):
    commit_msg = branch_name + '/' + commit_msg
    return commit_msg


def started_tag(branch_name):
    return get_tag_name(branch_name, '/started')


def testing_tag(branch_name):
    return get_tag_name(branch_name, '/testing')


def finished_tag(branch_name):
    return get_tag_name(branch_name, '/finished')


def released_tag(branch_name):
    return get_tag_name(branch_name, '/released')


def get_tag_name(branch_name, suffix):
    return branch_identifier(branch_name) + suffix


def approval_tag():
    return 'Approval_needed'


def overall_approval_tag():
    return 'Overall_approval_needed'


def branch_identifier(branch_name):
    if '/' in branch_name:
        branch_name = branch_name.split('/', 1)[1]
    return branch_name
