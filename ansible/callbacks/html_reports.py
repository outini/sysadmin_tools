# coding: utf-8
#
#  Ansible HTML reports callback (html_reports)
#
#  Copyright (C) 2020 Denis Pompilio (jawa) <denis.pompilio@gmail.com>
#
#  This file is part of html_reports
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the MIT License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  MIT License for more details.
#
#  You should have received a copy of the MIT License along with this
#  program; if not, see <https://opensource.org/licenses/MIT>.

from __future__ import (absolute_import, division, print_function)

import os
import json
import html
import random
from datetime import datetime
from collections import OrderedDict

from ansible.playbook.role_include import IncludeRole
from ansible.module_utils._text import to_bytes
from ansible.plugins.callback import CallbackBase


__metaclass__ = type

DOCUMENTATION = """
    callback: html_reports
    type: notification
    short_description: write playbook output to an html report
    version_added: 2.7
    description:
      - This callback writes playbook output to an html report
      - Reports are stored in the "./reports" directory
      - "TODO: make this configurable"
    requirements:
     - Python html package (`pip install --user html`)
     - Whitelist in configuration
"""

REPORT_HEAD = b"""\
<!doctype html>
<html lang="en">
  <head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">
    <style>
        body, .card { background-color: #fdf6e3; color: ##586e75; }
        .bd-navbar { position: sticky; top: 0; z-index: 1071; background-color: #002b36; }
        code { background-color: #002b36; color: #839496; }
        pre { margin: 0; padding: 5px; background-color: #002b36; color: #839496; }
        .card-body { margin: 0; padding: 0; }
        .item { padding: 5px; }
        .alert { margin-bottom: 5px; padding: 5px 5px; }
        .alert .alert { margin: 0; }
        .btn-sm { padding: 1px 4px; line-height: 1; }
        header .btn-sm { margin: 0 5px; }
    </style>
    <title>%s</title>
  </head>
  <body>
    <header class="navbar navbar-expand navbar-dark flex-column flex-md-row bd-navbar">
      <button class="btn btn-info btn-sm" type="button" data-toggle="collapse" data-target=".alert-info" aria-expanded="true">Show/Hide INFO</button>
      <button class="btn btn-info btn-sm" type="button" data-toggle="collapse" data-target=".alert-secondary" aria-expanded="true">Show/Hide SKIPPED</button>
      <button class="btn btn-info btn-sm" type="button" data-toggle="collapse" data-target=".alert-success" aria-expanded="true">Show/Hide OK</button>
      <!-- <button class="btn btn-info btn-sm" type="button" data-toggle="collapse" data-target=".blk-content" aria-expanded="true">Expand/Collapse ALL</button> -->
    </header>
    <!-- <div class="container-fluid"><main class="col-md-9 col-xl-8 py-md-3 pl-md-5 bd-content" role="main"> -->
"""

REPORT_FOOT = b"""\
    <!-- </main></div> -->
    <!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="https://code.jquery.com/jquery-3.4.1.slim.min.js" integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo" crossorigin="anonymous"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/js/bootstrap.min.js" integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6" crossorigin="anonymous"></script>
  </body>
</html>
"""

TIME_FORMAT = "%b %d %Y %H:%M:%S"

COLORS = OrderedDict(
    play='dark',
    skipped='secondary',
    include='info',
    ok='success',
    changed='warning',
    failed='danger',
    failures='danger',
    unreachable='danger'
)


def code_block(content):
    """Embed content in an HTML code block

    :param str content: Content to embed
    :return: Embedded content as :func:`str`
    """
    return "<code><pre>" + content + "</pre></code>"


def debug_block(data):
    """Embed data in an HTML debug block

    :param obj data: Data to embed
    :return: Json serialized embedded data as :func:`str`
    """
    return color_block(
        "skipped",
        "Debug",
        code_block(html.escape(json.dumps(data, indent=2)))
    )


def color_block(status, header=None, content=None):
    """"""
    color = COLORS[status]
    div_id = str(random.random())[2:]
    parts = ['<div class="alert alert-%s collapse show" role="alert">' % color]

    if header and content:
        parts.append('<a class="btn btn-%s btn-sm" data-toggle="collapse" '
                     'href="#x%s" role="button" aria-expanded="false" '
                     'aria-controls="x%s">+</a>' % (color, div_id, div_id))

    if header:
        parts.append("<strong>%s</strong>" % header)

    if header and content:
        parts.append('<div class="collapse blk-content" id="x%s">' % div_id)

    if content:
        parts.extend(['<div class="card card-body">',
                      content,
                      '</div>'
                      ])

    if header and content:
        parts.append('</div>')

    parts.append('</div>')
    return "\n".join(parts)


def cli_colors_to_html(text):
    """Convert CLI color codes to HTML colored tags

    :param str text: Text to convert
    :return: HTML colored text as :func:`str`
    """
    return html.escape(text) \
        .replace('[0;31m', '<code class="text-danger">') \
        .replace('[0;32m', '<code class="text-success">') \
        .replace('[0;36m', '<code class="text-info">') \
        .replace('[0m', '</code>')


def color_html(status, text):
    """Get HTML colored representation of text

    :param str status: Status to use for color selection
    :param str text: Text to color
    :return: Colored HTML representation of text as :func:`str`
    """
    color = COLORS[status]
    return '<code class="text-%s">%s</code>' % (color, html.escape(text))


def strip_internal_keys(result):
    """Clean internal keys from Ansible result

    :param obj result: Ansible result
    :return: Cleaned Ansible result
    """
    if isinstance(result, list):
        for element in result:
            if isinstance(element, (dict, list)):
                strip_internal_keys(element)
    elif isinstance(result, dict):
        for k in list(result.keys()):
            if isinstance(k, str):
                if k.startswith('_ansible_'):
                    del result[k]
                    continue
            if isinstance(result[k], (dict, list)):
                strip_internal_keys(result[k])
    else:
        pass
    return result


def highest_status(status, results_list):
    """Get highest status from a result list

    :param str status: Initial status
    :param list results_list: Ansible results list
    :return: Highest status as :func:`str`
    """
    s_order = list(COLORS.keys())
    for r in list(results_list):
        if not status \
           or s_order.index(r['status']) > s_order.index(status):
            status = r['status']
    return status


class TaskData(object):
    """Ansible task essential data object

    :param Play play: Ansible Play object the task is related to
    :param Task task: Task object from Ansible hooks
    :param str prefix: Task prefix (ie. TASK or HANDLER)
    """
    def __init__(self, play, task, prefix="TASK"):
        self._play = play
        self.start = datetime.now()
        self.name = task.get_name()
        self.file = task.get_path()
        self.prefix = prefix
        self._status = None
        self.results = OrderedDict()

        # variables for local includes only
        self.include_filepath = None
        self.include_args = ""
        self.include_hosts = None

        if isinstance(task, IncludeRole):
            self.task_type = "IncludeRole"
            self._status = "include"
        else:
            self.task_type = "Task"

    def __repr__(self):
        return "%s %s (%s)" % (self.prefix, self.name, self.status)

    @property
    def status(self):
        """Task status property computed from task results

        :return: Task status as :func:`str`
        """
        if not self._status:
            self._status = highest_status(self._status, self.results.values())
        if not self._status:
            self._status = "skipped"
        return self._status

    @property
    def header(self):
        """Task header property

        :return: Task header as :func:`str`
        """
        now = self.start.strftime(TIME_FORMAT)
        header = "%s: %s - %s: %s" % (now, self.status, self.prefix, self.name)
        if self.task_type == "IncludeRole":
            header += " (include role)"
        return header

    def get_diff(self, result, status):
        """Get essential diffs data from Ansible result

        :param dict result: Ansible task result dict from TaskResult object
        :param str status: Related task status
        :return: Diffs essential data as :func:`list` of :obj:`dict`
        """
        # convert to list so we might handle every cases the same way
        result = result['results'] if 'results' in result else [result]

        diffs = []
        for res in result:
            failed = res['failed'] if "failed" in res else status == "failed"
            diffs.append({
                'item': res.get('item'),
                'changed': res.get('changed', False),
                'failed': failed,
                'msg': res.get('msg'),
                'diff': self._play._get_diff(res.get('diff', []))
            })
        return diffs

    def record_local_include(self, included_file):
        """Register local include tasks

        :param obj included_file: Included file object from Ansible hooks
        """
        self.task_type = "LocalInclude"
        self._status = "include"
        self.include_filepath = included_file._filename
        if 'item' in included_file._args:
            self.include_args = self._play._get_item_label(included_file._args)
        self.include_hosts = [h.name for h in included_file._hosts]

    def record_result(self, result, status):
        """Register a new task result

        :param TaskResult result: Task result object from Ansible hooks
        :param str status: Task result status
        """
        result_id = result._host.get_name() + "-" + result._task.get_name()
        if result_id not in self.results:
            self.results[result_id] = {}

        self.results[result_id].update({
            'datetime': datetime.now(),
            'host': result._host.get_name(),
            'status': status,
            'task_name': result._task.get_name(),
            'deleg_vars': result._result.get('_ansible_delegated_vars', None),
            'diffs': self.get_diff(result._result, status),
            'result': strip_internal_keys(result._result)
        })

    def to_html(self):
        """Get HTML representation of this object

        :return: HTML representation as :func:`str`
        """
        if self.task_type == "LocalInclude":
            html_content = code_block(
                "Included file: %s\n"
                "Hosts:\n"
                "%s" % (
                    "%s%s" % (self.include_filepath, self.include_args),
                    "\n".join([h for h in self.include_hosts]),
                )
            )
            return color_block(self.status, self.header, html_content)

        html_content = ""
        for result in self.results.values():

            header = "%s: %s" % (result['status'], result['host'])

            if result['deleg_vars']:
                header += " => %s" % result['deleg_vars']['ansible_host']

            # reset "ok" status to "include" for successful includes
            if result['status'] == "ok" and self.status == "include":
                result['status'] = self.status

            # If status is skipped or include, do not show details
            if result['status'] in ["skipped", "include"]:
                html_content += color_block(
                    result['status'],
                    header=html.escape(header)
                )

            else:
                content = ""
                for diff in result.get('diffs', []):
                    if diff['item']:
                        item = '<div class="item">Item: %s</div>\n' % (
                            html.escape(str(diff['item'])))
                    else:
                        item = ""

                    if diff['failed']:
                        content += color_block(
                            "failed",
                            content='%s<div class="item">Msg: %s</div>' % (
                                item, html.escape(str(diff['msg']))))

                    elif not diff['changed']:
                        if item:
                            content += color_block("ok", content=item)

                    else:
                        if diff['diff']:
                            diff = code_block(
                                cli_colors_to_html(diff['diff'])
                            )
                        else:
                            diff = ""
                        if item or diff:
                            content += color_block(
                                result['status'], content='%s%s' % (item, diff)
                            )

                html_content += color_block(
                    result['status'],
                    html.escape(header),
                    content + debug_block({'task_file': self.file,
                                           'result': result['result']})
                )

        return color_block(self.status, self.header, html_content)


class CallbackModule(CallbackBase):
    """Writes playbook results, per host, in an HTML report
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'html_reports'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()

        self._play = None
        self._stats = None
        self.reports_path = "reports"
        self.start = datetime.now()
        self.stop = None
        self.name = None
        self.check_mode = False
        self.tasks = []

    @property
    def summary(self):
        """HTML summary property of the PLAY object

        :return: HTML summary as :func:`str`
        """
        if self._stats:
            status = ['ok', 'changed', 'unreachable', 'failures']
            sum_status = dict(zip(status, [0, 0, 0, 0]))
            text = ""
            for host in sorted(self._stats.processed.keys()):
                t = self._stats.summarize(host)
                host_color = [s for s in status if t[s]][-1]
                text += "%s : " % color_html(host_color, host)
                for s in status:
                    sum_status[s] += t[s]
                    entry = "%s=%s  " % (s, t[s])
                    text += color_html(s, entry) if t[s] else entry
                text += "\n"
            sum_line = "Hosts: %d\nSummary: " % len(self._stats.processed)
            for s, n in sum_status.items():
                entry = "%s=%s  " % (s, n)
                sum_line += color_html(s, entry) if n else entry
            return sum_line + "\n" + text
        return ""

    @summary.setter
    def summary(self, stats):
        """Summary property setter

        :param obj stats: Stats object from Ansible hooks
        """
        self._stats = stats
        self.stop = datetime.now()

    def new_task(self, task, prefix="TASK"):
        """Record a new task

        :param Task task: Task object from Ansible hooks
        :param str prefix: Task prefix (ie. TASK or HANDLER)
        """
        self.tasks.append(TaskData(self, task, prefix))

    def record_task_result(self, result, status):
        """Register a new task result

        :param TaskResult result: Task result object from Ansible hooks
        :param str status: Task result status
        """
        self.tasks[-1].record_result(result, status)

    def to_html(self):
        """Get HTML representation of this object

        :return: HTML representation as :func:`str`
        """
        content = ""
        header = "PLAY: " + self.name
        if self.check_mode:
            header += "  [check mode]"
        content += color_block(
            'play',
            header,
            code_block(
                "Start: %s\n"
                "Stop: %s\n"
                "Duration: %d seconds\n"
                "Tasks: %d\n"
                "%s" % (
                    self.start.strftime(TIME_FORMAT),
                    self.stop.strftime(TIME_FORMAT),
                    (self.stop - self.start).seconds,
                    len(self.tasks),
                    self.summary)
            )
        )
        for task in self.tasks:
            content += task.to_html()
        return content

    def write_report(self):
        """Generate, and write HTML report on disk
        """
        report_name = "ansible-report-%s.html" % (
            self.start.strftime("%Y%m%d-%H%M%S")
        )

        if not os.path.exists(self.reports_path):
            os.makedirs(self.reports_path)
        path = os.path.join(self.reports_path, report_name)

        with open(path, "wb") as report_fd:
            report_fd.write(REPORT_HEAD % report_name.encode())
            report_fd.write(to_bytes(self.to_html()))
            report_fd.write(REPORT_FOOT)

    def v2_playbook_on_play_start(self, play):
        self.name = play.get_name().strip()
        self.check_mode = play.check_mode
        self._play = play

    def v2_playbook_on_stats(self, stats):
        self.summary = stats
        self.write_report()

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.new_task(task, prefix="TASK")

    def v2_playbook_on_handler_task_start(self, task):
        self.new_task(task, prefix="HANDLER")

    def v2_playbook_on_include(self, included_file):
        self.tasks[-1].record_local_include(included_file)

    def v2_runner_on_failed(self, result, ignore_errors):
        self.record_task_result(result, "failed")

    def v2_runner_on_ok(self, result):
        status = "changed" if result.is_changed() else "ok"
        self.record_task_result(result, status)

    def v2_runner_on_skipped(self, result):
        self.record_task_result(result, "skipped")

    def v2_runner_on_unreachable(self, result):
        self.record_task_result(result, "unreachable")

    def v2_runner_on_async_failed(self, result):
        self.record_task_result(result, "failed")

    def v2_playbook_on_import_for_host(self, result, imported_file):
        self.record_task_result(result, "include")

    def v2_playbook_on_not_import_for_host(self, result, missing_file):
        self.record_task_result(result, "failed")
