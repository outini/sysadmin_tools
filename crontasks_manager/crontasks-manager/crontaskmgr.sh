#! /bin/sh

#
# This script comes with no warranty ...use at own risk
# Copyright (C) 2013  Denis Pompilio
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program or from the site that you downloaded it
# from; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA  02111-1307   USA
#
# Use this script to schedule "stop" days for your crontasks.
# The default file "default_stop_days.cfg" is used to register
# forbidden days. Specific "stop days" files could be specified
# for running specific crontasks.
#
#

# error codes
EXIT_USAGE=1
EXIT_STOPDAY=2
EXIT_ERROR=3

script_path=`cd $(dirname ${0}) && pwd`
logfile=/data/www/client/logs/crontasks-manager/crontask-manager.log

usage() {
    cat <<EOF >&2
Usage: $0 [options]

Use this script to schedule "stop" days for your crontasks.
Default file "default_stop_days.cfg" is used to register
forbidden days. Specific "stop days" files could be specified
for running particular crontasks.

"stop days" file syntax have to be respected with one date per
line. Any syntax invalid lines will be ignored silently. the
"validate" options with explicitly check every line from file.

stop days file date format: YYYY/MM/DD

When using this script to run crontasks, a check is done against
the stop days file and the run of task is aborted if current day
is found.

The run option is mandatory to run crontask. This is a security
to disable the accidental run of a crontask.

The stop days files could be specified with relative path. First check
is done with the specified path, fallback search is done in the script
directory.

Actual script directory: $script_path

Options:
    --help|-h        Show this help (default action if no arguments)
    --validate|-c    Validate stop days file syntax
    --quiet|-q       Disable display crontask execution output on console
    --stopfile|-f    Specify a stop days file
                     (default is default_stop_days.cfg)
    --run|-r         Specify the crontask to run
                     Options parsing is stopped by this argument and any
                     arguments that last is used for the crontask definition

Exemple:
    $0 --validate
    $0 --validate -f specific_stop_days.cfg
    $0 -r php /path/to/crontask.php --crontask-argument

EOF
    exit $EXIT_USAGE
}

success() {
    echo "SUCCESS: $@" >&2
}
error() {
    echo "ERROR: $@" >&2
    exit $EXIT_ERROR
}

log() {
    now=`date +%Y%m%d-%H%M%S`
    echo "${now}: $@" >> "${logfile}"
    $quiet || echo "${now}: $@"
}

validate() {
    local stopfile="$1"

    syntax_error=0
    line_num=0
    while read line ; do
	: $((line_num++))

	date -d "$line" 2>/dev/null 1>/dev/null || {
	    echo "syntax error on line ${line_num}: $line"
	    syntax_error=1
	}
    done < "${stopfile}"

    return $syntax_error
}

quiet=false
validate=false
stopfile="${script_path}/default_stop_days.cfg"

[ $# -le 0 ] && usage
while [ $# -gt 0 ] ; do
    case "$1" in
	"--validate"|"-c") validate=true; shift ;;
	"--quiet"|"-q") quiet=true; shift ;;
	"--stopfile"|"-f") stopfile="$2"; shift 2 ;;
	"--run"|"-r") shift; break ;;
	"--help"|"-h"|*) usage ;;
    esac
done

[ -f "${stopfile}" ] || {
    [ -f "${script_path}/${stopfile}" ] &&
    stopfile="${script_path}/${stopfile}"
} || error "file '$stopfile' not found"

$validate && {
    validate "$stopfile" &&
    success "syntax validation succeed" ||
    error "syntax validation failed"
}

today=`date +%Y/%m/%d`
grep -q "$today" "$stopfile" && exit $EXIT_STOPDAY

[ -z "$*" ] || {
    log "running: $@"
    eval "$@"
    log "stopped: $@"
}
