#! /usr/bin/env python3
# coding: utf-8
#
#  Cisco NXOS configuration reader (nxos_reader)
#
#  Copyright (C) 2019 Denis Pompilio (jawa) <denis.pompilio@gmail.com>
#
#  This file is part of nxos_reader
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

import argparse
import json
import netmiko


VERSION = "0.3.0"


class UnsupportedFeature(RuntimeError):
    def __init__(self, feature):
        self.msg = "Unsupported feature: " + feature

    def __repr__(self):
        return self.msg

    def __str__(self):
        self.__repr__()


class Entry(dict):
    """"""

    def to_json(self):
        output = ["name: '{vlan_name}'", "vlan_id: {vlan_id}"]

        if self['vni'] is not None:
            output.extend([
                "vrf: '{vrf}'",
                "isL3: {isl3}",
                "vni: {vni}"
            ])
            if self['isl3'] is False:
                output.extend(["gwip: {masterip}", "mask: {mask} "])
        elif self['masterip']:
            output.extend([
                "vrf: '{vrf}'",
                "masterip: {masterip}",
                "slaveip: {slaveip}",
                "mask: {mask}"
            ])
            if self['vip']:
                output.extend(["vip: {vip}"])

        return "- { " + ", ".join(output).format(**self) + " }"


class Nexus(object):
    """"""

    def __init__(self, conn_str):
        """"""
        self.user, self.fqdn = conn_str.split('@', 1)
        self.device = {
            'device_type': 'cisco_nxos',
            'host': self.fqdn,
            'username': self.user,
            "allow_agent": True
        }
        self._conn = None
        self._mac_addrs = None
        self._vlans = None
        self._vrfs = None
        self._vrf_ifaces = None
        self._interfaces = None
        self._hsrp = None
        self._vxlan = None

    @property
    def conn(self):
        """"""
        if not self._conn:
            self._conn = netmiko.ConnectHandler(**self.device)
        return self._conn

    @property
    def mac_addrs(self):
        if not self._mac_addrs:
            out = self.conn.send_command("show mac address-table | json")
            self._mac_addrs = json.loads(out)['TABLE_mac_address']
        return self._mac_addrs['ROW_mac_address']

    @property
    def vlans(self):
        if not self._vlans:
            out = self.conn.send_command("show vlan all | json")
            self._vlans = json.loads(out)['TABLE_vlanbriefallports']
        return self._vlans['ROW_vlanbriefallports']

    @property
    def interfaces(self):
        if not self._interfaces:
            out = self.conn.send_command("show interface | json")
            self._interfaces = json.loads(out)["TABLE_interface"]
        return self._interfaces["ROW_interface"]

    def get_interface(self, name):
        for iface in self.interfaces:
            if name == iface["interface"]:
                return iface
        return {}

    @property
    def vrfs(self):
        if not self._vrfs:
            out = self.conn.send_command("show vrf all | json")
            self._vrfs = json.loads(out)["TABLE_vrf"]
        return self._vrfs["ROW_vrf"]

    @property
    def vrf_ifaces(self):
        if not self._vrf_ifaces:
            out = self.conn.send_command("show vrf all interface | json")
            self._vrf_ifaces = json.loads(out)["TABLE_if"]
        return self._vrf_ifaces["ROW_if"]

    def get_vrf(self, iface_name):
        vrf_name = "default"
        for vrf in self.vrf_ifaces:
            if vrf['if_name'] == iface_name:
                vrf_name = vrf['vrf_name']
        return vrf_name

    def get_vlan_macs(self, vlan_id, skip_local=True):
        for mac in [m for m in self.mac_addrs if m['disp_vlan'] == vlan_id]:
            if skip_local and mac['disp_type'] in ['G']:
                continue
            yield mac

    @property
    def hsrp(self):
        if not self._hsrp:
            out = self.conn.send_command("show hsrp all | json")
            if "% Invalid command" in out:
                raise UnsupportedFeature("hsrp")
            self._hsrp = json.loads(out)["TABLE_grp_detail"]
        return self._hsrp['ROW_grp_detail']

    def get_hsrp(self, iface_name):
        for hsrp in self.hsrp:
            if hsrp['sh_if_index'] == iface_name:
                return hsrp
        return {}

    @property
    def vxlan(self):
        if not self._vxlan:
            self._vxlan = {}
            out = self.conn.send_command("show vxlan")
            for line in out.splitlines():
                if line.startswith('Vlan') or line.startswith('===='):
                    continue
                vlan_id, vni = line.split(None, 1)
                self._vxlan[vlan_id] = vni
        return self._vxlan


def gather_data(conn_str_a, conn_str_b, vxlan=False):
    m_sw = Nexus(conn_str_a)
    if conn_str_b:
        s_sw = Nexus(conn_str_b)

    entries = []
    for vlan in m_sw.vlans:
        vlan_id = vlan['vlanshowbr-vlanid']
        iface_name = "Vlan" + vlan_id
        iface = m_sw.get_interface(iface_name)

        vrf_name = m_sw.get_vrf(iface_name)
        mask = iface.get("svi_ip_mask")

        slaveip = None
        vip = None
        isl3 = None
        vni = None

        if not vxlan:
            hsrp = m_sw.get_hsrp(iface_name)
            masterip = hsrp.get('sh_active_router_addr')
            slaveip = hsrp.get('sh_standby_router_addr')
            vip = hsrp.get('sh_vip')

            if not masterip:
                masterip = iface.get('svi_ip_addr')
                s_iface = s_sw.get_interface(iface_name)
                if s_iface:
                    slaveip = s_iface.get('svi_ip_addr')
        else:
            vni = m_sw.vxlan.get(vlan_id)
            masterip = iface.get('svi_ip_addr')
            isl3 = False if masterip else True

        entries.append(Entry(
            vlan_id=vlan_id,
            vlan_name=vlan['vlanshowbr-vlanname'],
            vrf=vrf_name,
            vni=vni,
            masterip=masterip,
            slaveip=slaveip,
            vip=vip,
            mask=mask,
            isl3=isl3
        ))
    return entries


def show_vlans_macs(conn_str):
    m_sw = Nexus(conn_str)
    for vlan in m_sw.vlans:
        vlan_id = vlan['vlanshowbr-vlanid']
        print("vlan %s mac addresses count: %d" % (
            vlan_id,
            len(list(m_sw.get_vlan_macs(vlan_id)))
        ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Cisco NXOS configuration reader')

    parser.add_argument('--version', dest='version', action='store_const',
                        const=True, default=False,
                        help='show script version')
    parser.add_argument('-m', '--connect-master', dest='m_conn',
                        help='specify a connection string user@device')
    parser.add_argument('-s', '--connect-slave', dest='s_conn',
                        help='specify a connection string user@device')
    parser.add_argument('--vxlan', action="store_true", default=False,
                        help='use vxlan mode, ignore hsrp and slave target')
    parser.add_argument('-t', '--targets-file', dest="targets_file",
                        help='specify a file listing connection strings,'
                             ' one per line, master and slave being splitted'
                             ' by "|"')
    parser.add_argument('-e', '--vlans-macs', dest="vlans_macs",
                        action="store_true",
                        help='show discovered macs per vlan')

    args = parser.parse_args()

    if args.version:
        print("Script version: %s" % VERSION)
        exit()

    targets = None
    if args.targets_file:
        targets = open(args.targets_file).readlines()
    elif not args.m_conn:
        parser.error('master connection string not provided')
        exit(1)
    elif not args.s_conn:
        try:
            assert args.vxlan or args.vlans_macs
        except AssertionError:
            parser.error('slave connection string not provided')
            exit(1)

    if targets is not None:
        entries = {}
        for line in targets:
            target = line.strip().split('|', 1)
            master = target[0]
            slave = target[1] if len(target) == 2 else None

            try:
                if args.vlans_macs:
                    show_vlans_macs(master)
                    continue

                data = gather_data(master, slave, args.vxlan)
            except:
                print("# unresponsive targets: " + line.strip())
                continue

            for entry in data:
                if entry['vlan_id'] not in entries:
                    entries[entry['vlan_id']] = entry

        for entry in entries.values():
            print(entry.to_json())

    else:
        if args.vlans_macs:
            show_vlans_macs(args.m_conn)
            exit(1)

        data = gather_data(args.m_conn, args.s_conn, args.vxlan)
        for entry in data:
            print(entry.to_json())
