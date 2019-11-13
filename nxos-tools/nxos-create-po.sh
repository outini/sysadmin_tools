#! /usr/bin/env bash


SW_USER="$USER"

NXOS_LIST_PO="show port-channel summary | grep '^[1-9]'"
NXOS_SHOW_IF_CFG="show running-config interface"

# locally store port-channel lists to limit ssh connections
declare -A PO_LIST


usage() {
    [ -z "${1}" ] || echo "${@}" >&2
    cat >&2 <<EOU
Usage:
    ${0} [-h] <options>

Options:
    -d <desc>       description to set on interfaces
                    Optional in case of port-channel purge

    -a <fqdn>       first switch fqdn or IP to configure
    -A <ports>      ports to aggregate on first switch

    -b <fqdn>       [OPTIONAL] second switch fqdn or IP to configure
    -B <ports>      [OPTIONAL] ports to aggregate on second switch
                      this argument is mandatory with '-b' if not '-p'

    -u <user>       [OPTIONAL] specify the user to connect on switches

    -t              [OPTIONAL] set the port-channel in trunk mode (default)
    -T              [OPTIONAL] set the port-channel in access mode

    -l <id>         vlan ID for access mode, of native vlan ID for trunk mode
    -L <id,id,...>  [OPTIONAL] allowed vlan IDs when in trunk mode

    -s <PoX>        [OPTIONAL] show specified port channel configuration
    -p <N>          [OPTIONAL] purge specified port channel from configuration
                      only the port-channel number has to be specified

    -h              show this help

Environment:
    DEBUG=true      activate the debug logging on stderr
EOU
    exit 1
}

debug() {
    ${DEBUG:-false} || return
    echo "[DEBUG] $*" >&2
}

info() {
    echo "[INFO] $*" >&2
}

warning() {
    echo "[WARNING] $*" >&2
}

exit_err() {
    echo "[ERROR] $*"
    exit 2
}

sw_run_cmds() {
    local switch="${1}"; shift
    debug "${switch}: running command: ${@}"
    ssh -T -l "${SW_USER}" "${switch}" "${@}" 2> >(
        grep -v 'User Access Verification' \
             -v 'stty: standard input: Invalid argument'
    )
}

list_po() {
    local switch="${1}"
    local portchannel="${2}"
    [ -n "${PO_LIST[${switch}]}" ] || {
        debug "listing all port-channels on ${switch}"
        PO_LIST[${switch}]=$(sw_run_cmds ${switch} "${NXOS_LIST_PO}")
    }
    while read group po itype proto members; do
        debug "${group} ${po} ${itype} ${proto} ${members}"
        local ifaces=
        for member in ${members}; do
            ifaces+="${member%%\(*} "
        done
        ifaces=${ifaces% }  # clean the trailing space
        [ -n "${portchannel}" ] || echo "${group} ${po%%\(*} ${ifaces}"
        [ -n "${portchannel}" ] && [ "${portchannel}" = "${po%%\(*}" ] &&
            echo "${group} ${po%%\(*} ${ifaces// /,}"
    done <<< "${PO_LIST[${switch}]}"
}

show_po() {
    local portchannel="${1}"; shift
    local switches="$@"
    for switch in ${*}; do
        echo "## switch: ${switch}"
        read _ po ifaces <<<$(list_po "${switch}" "${portchannel}")
        [ -n "${po}" ] || {
            warning "interface ${portchannel} not found"
            continue
        }
        {
            sw_run_cmds "${switch}" "${NXOS_SHOW_IF_CFG} ${portchannel}"
            sw_run_cmds "${switch}" "${NXOS_SHOW_IF_CFG} ${ifaces// /,}"
        } | sed -n '/^interface /{:n;N;/\n$/!bn;p;}'
    done
}

find_next_po() {
    declare -A ifaces
    debug "finding next available port-channel number"
    for switch in "${@}"; do
        [ -n "${ifaces[${switch}]}" ] ||
            while read _ po _; do
                ifaces[${switch}]+="${po} "
            done <<< $(list_po "${switch}")
    done
    for n in $(seq 2 4000); do
        [[ "${ifaces[*]}" = *" Po${n} "* ]] || { echo "${n}"; break; }
    done
    debug "port-channel number ${n} is available"
}

create_po() {
    local desc="${1}"
    local ifaces="${2}"
    local po="${3}"
    local nvlan="${4}"
    local avlan="${5}"
    local trunk="${6}"

    echo "conf t"

    echo "interface ${ifaces}"
    echo "  description ${desc}"
    echo "  switchport"
    echo "  channel-group ${po} mode passive"
    echo "  no shutdown"

    echo "interface port-channel ${po}"
    echo "  description ${desc}"
    echo "  switchport"

    if ${trunk:-true}; then
        echo "  switchport mode trunk"
        echo "  switchport trunk native vlan ${nvlan}"
        [ -n "${avlan}" ] &&
        echo "  switchport trunk allowed vlan ${nvlan},${avlan}"
    else
        echo "  switchport mode access"
        echo "  switchport access vlan ${nvlan}"
    fi
    echo "  no lacp suspend-individual"
    echo "  spanning-tree port type edge trunk"
    echo "  vpc ${po}"
    echo "  no shutdown"

    echo "end"
}

purge_po() {
    local po="${1}"
    local switch="${2}"

    read _ _ ifaces <<<$(list_po "${switch}" "Po${po}")

    echo "configure terminal"
    echo "no interface port-channel ${po}"
    echo "default interface ${ifaces:---}"
    echo "end"
}


## MAIN ######################################################################
#

unset OPTIND  # bash(1): The shell does not reset OPTIND automatically
while getopts :hs:p:d:a:b:A:B:u:tTl:L: opt; do
    case "${opt}" in
        s) show="${OPTARG}" ;;
        p) purge="${OPTARG}" ;;
        d) description="${OPTARG}" ;;
        a) switch_a="${OPTARG}" ;;
        b) switch_b="${OPTARG}" ;;
        A) switch_ports_a="${OPTARG}" ;;
        B) switch_ports_b="${OPTARG}" ;;
        u) sw_user="${OPTARG}" ;;
        t) trunk=true ;;
        T) trunk=false ;;
        l) l2_native_vlan="${OPTARG}" ;;
        L) l2_allowed_vlan="${OPTARG}" ;;
        h) usage ;;
        \?) usage "Unknown option ${OPTARG}" ;;
        :) usage "Option -${OPTARG} requires an argument." ;;
    esac
done

# TODO: implement the access mode
${trunk:-true} || exit_err "access mode is not implemented yet :/"

[ -n "${sw_user}" ] && SW_USER="${sw_user}" || SW_USER="$USER"
[ -n "${switch_a}" ] || usage "provide at least one switch to connect to"

# load the port-channel lists to limit ssh connections
list_po ${switch_a} >/dev/null
[ -n "${switch_b}" ] && list_po ${switch_b} >/dev/null

# handle the show as soon as possible, then exit
if [ -n "${show}" ]; then
    show_po "${show}" "${switch_a}" "${switch_b}"
    exit 0
fi

# handle the purge as soon as possible, then exit
if [ -n "${purge}" ]; then
    purge_po "${purge}" "${switch_a}" | sw_run_cmds "${switch_a}"
    [ -n "${switch_b}" ] &&
    purge_po "${purge}" "${switch_b}" | sw_run_cmds "${switch_b}"
    info "port-channel ${purge} has been purged"
    exit 0
fi

# handle port-channel creation (more complex)
[ -n "${description}" ] || exit_err "provide a port description"
[ -n "${l2_native_vlan}" ] || exit_err "provide a native vlan ID"
${trunk:-true} && {
    [ -n "${l2_allowed_vlan}" ] || exit_err "provide allowed vlan IDs"
}
[ -n "${switch_ports_a}" ] || exit_err "provide ports for first switch"
[ -n "${switch_b}" ] && {
    [ -n "${switch_ports_b}" ] || exit_err "provide ports for second switch"
}

avail_po=$(find_next_po ${switch_a} ${switch_b})
[ -n "$avail_po" ] || exit_err "no available port-channel number"

create_po "${description}" "${switch_ports_a}" "${avail_po}" \
          "${l2_native_vlan}" "${l2_allowed_vlan}" ${trunk} |
sw_run_cmds "${switch_a}"

[ -n "${switch_b}" ] &&
create_po "${description}" "${switch_ports_b}" "${avail_po}" \
          "${l2_native_vlan}" "${l2_allowed_vlan}" ${trunk} |
sw_run_cmds "${switch_b}"

info "port-channel ${avail_po} created"
