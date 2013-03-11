#
#

# Copyright (C) 2013 Google Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.


"""QA tests for networks.

"""

import qa_config
import qa_tags
import qa_utils

from ganeti import query

from qa_utils import AssertCommand

TEST_NET_1 = "192.0.2.0/24"
TEST_NET_2 = "198.51.100.0/24"
TEST_NET_3 = "203.0.113.0/24"

TEST_NET6_1 = "2001:648:2ffc:1201::/64"
GW_IN_NET6_1 = "2001:648:2ffc:1201::1"
IP_IN_NET6_1 = "2001:648:2ffc:1201::81"

TEST_NET6_2 = "2002:648:2c:101::/64"
GW_IN_NET6_2 = "2002:648:2c:101::1"
IP_IN_NET6_2 = "2002:648:2c:101::54"

GW_IN_NET_1 = "192.0.2.1"
GW2_IN_NET_1 = "192.0.2.100"
GW_IN_NET_2 = "198.51.100.1"
GW_IN_NET_3 = "203.0.113.1"
IP_IN_NET_1 = "192.0.2.50"
IP2_IN_NET_1 = "192.0.2.70"
IP_IN_NET_2 = "198.51.100.82"
IP_IN_NET_3 = "203.0.113.118"


def TestNetworkList():
  """gnt-network list"""
  qa_utils.GenericQueryTest("gnt-network", query.NETWORK_FIELDS.keys())


def TestNetworkListFields():
  """gnt-network list-fields"""
  qa_utils.GenericQueryFieldsTest("gnt-network", query.NETWORK_FIELDS.keys())


def GetNicParams():
  default_mode = "bridged"
  default_link = "br0"
  nicparams = qa_config.get("default-nicparams")
  if nicparams:
    mode = nicparams.get("mode", default_mode)
    link = nicparams.get("link", default_link)
  else:
    mode = default_mode
    link = default_link

  return mode, link


def GetNetOption(idx=-1, action=None, mac=None, ip=None, network=None,
                 mode=None, link=None):
  net = "%d:" % idx
  if action:
    net += action
  if mac:
    net += ",mac=" + mac
  if ip:
    net += ",ip=" + ip
  if network:
    net += ",network=" + network
  if mode:
    net += ",mode=" + mode
  if link:
    net += ",link=" + link

  return net.replace(":,", ":")


def RemoveInstance(instance):
  name = instance.name
  AssertCommand(["gnt-instance", "remove", "-f", name])
  instance.Release()


def GetInstance():
  return qa_config.AcquireInstance()


def LaunchInstance(instance, mac=None, ip=None, network=None,
                   mode=None, link=None, fail=False):

  name = instance.name
  templ = qa_config.GetDefaultDiskTemplate()
  net = GetNetOption(0, None, mac, ip, network, mode, link)
  AssertCommand(["gnt-instance", "add", "-o", qa_config.get("os"),
                 "-t", templ, "--disk", "0:size=1G", "--net", net,
                 "--no-name-check", "--no-ip-check", "--no-install", name],
                 fail=fail)


def ModifyInstance(instance, idx=-1, action="add", mac=None,
                   ip=None, network=None, mode=None, link=None, fail=False):

  name = instance.name
  net = GetNetOption(idx, action, mac, ip, network, mode, link)
  AssertCommand(["gnt-instance", "modify", "--net", net, name], fail=fail)


def TestNetworkAddRemove():
  """gnt-network add/remove"""
  (network1, network2, network3) = qa_utils.GetNonexistentNetworks(3)

  # Note: Using RFC5737 addresses.
  # Add a network without subnet
  AssertCommand(["gnt-network", "add", network1])
  AssertCommand(["gnt-network", "remove", network1])
  # remove non-existing network
  AssertCommand(["gnt-network", "remove", network2], fail=True)

  # Check wrong opcode parameters
  # wrone cidr notation
  AssertCommand(["gnt-network", "add", "--network", "xxxxx", network1],
                fail=True)
  # gateway outside the network
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1,
                 "--gateway", GW_IN_NET_2, network1],
                fail=True)
  # v6 gateway but not network
  #AssertCommand(["gnt-network", "add", "--gateway6", IP_IN_NET6_1, network1],
  #              fail=False)
  # gateway but not network
  #AssertCommand(["gnt-network", "add", "--gateway", IP_IN_NET_1, network1],
  #              fail=False)
  # wrong mac prefix
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1,
                 "--mac-prefix", "xxxxxx", network1],
                fail=True)

  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1,
                 "--gateway", GW_IN_NET_1, "--mac-prefix", "aa:bb:cc",
                 "--add-reserved-ips", IP_IN_NET_1,
                 "--network6", TEST_NET6_1,
                 "--gateway6", GW_IN_NET6_1, network1])

  # TODO: add a network that contains the nodes' IPs
  # This should reserve them
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_2,
                 network2])

  # This does not reserve master/node IPs
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_3,
                 "--no-conflicts-check", network3])

  # Try to add a network with an existing name.
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1, network2],
                fail=True)

  TestNetworkList()
  TestNetworkListFields()

  AssertCommand(["gnt-network", "remove", network1])
  AssertCommand(["gnt-network", "remove", network2])
  AssertCommand(["gnt-network", "remove", network3])


def TestNetworkSetParams():
  """gnt-network modify"""
  (network1, ) = qa_utils.GetNonexistentNetworks(1)

  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1,
                 "--gateway", GW_IN_NET_1, "--mac-prefix", "aa:bb:cc",
                 "--add-reserved-ips", IP_IN_NET_1,
                 "--network6", TEST_NET6_1,
                 "--gateway6", GW_IN_NET6_1, network1])

  # Cannot modify subnet
  AssertCommand(["gnt-network", "modify", "--network", TEST_NET_2,
                 network1], fail=True)

  # Gateway outside network
  AssertCommand(["gnt-network", "modify", "--gateway", IP_IN_NET_2,
                 network1], fail=True)

  # Gateway with reserved ips
  AssertCommand(["gnt-network", "modify", "--gateway", GW2_IN_NET_1,
                 "--add-reserved-ips", IP2_IN_NET_1,
                 network1], fail=True)

  # Edit all
  # TODO: test reserved ips
  AssertCommand(["gnt-network", "modify", "--gateway", GW2_IN_NET_1,
                 "--network6", TEST_NET6_2,
                 "--gateway6", GW_IN_NET6_2,
                network1])

  # reset everything
  AssertCommand(["gnt-network", "modify", "--gateway", "none",
                 "--network6", "none", "--gateway6", "none",
                 "--mac-prefix", "none",
                 network1])

  AssertCommand(["gnt-network", "remove", network1])

  TestNetworkList()


def TestNetworkTags():
  """gnt-network tags"""
  (network, ) = qa_utils.GetNonexistentNetworks(1)
  AssertCommand(["gnt-network", "add", "--network", "192.0.2.0/30", network])
  qa_tags.TestNetworkTags(network)
  AssertCommand(["gnt-network", "remove", network])


def TestNetworkConnect():
  """gnt-network connect/disconnect"""
  (group1, group2, ) = qa_utils.GetNonexistentGroups(2)
  (network1, network2, ) = qa_utils.GetNonexistentNetworks(2)
  defmode, deflink = GetNicParams()

  AssertCommand(["gnt-group", "add", group1])
  AssertCommand(["gnt-group", "add", group2])
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1, network1])
  AssertCommand(["gnt-network", "add", "--network", TEST_NET_2, network2])

  AssertCommand(["gnt-network", "connect", network1,
                 defmode, deflink, group1])
  # This should produce a warning for group1
  AssertCommand(["gnt-network", "connect", network1, defmode, deflink])
  # Network still connected
  AssertCommand(["gnt-network", "remove", network1], fail=True)

  instance1 = GetInstance()
  # Add instance inside the network
  LaunchInstance(instance1, ip="pool", network=network1)
  # Conflicting IP, at least one instance belongs to the network
  AssertCommand(["gnt-network", "disconnect", network1], fail=True)
  RemoveInstance(instance1)

  RemoveInstance(instance1)
  AssertCommand(["gnt-group", "remove", group1])
  AssertCommand(["gnt-group", "remove", group2])
  AssertCommand(["gnt-network", "remove", network1])
  AssertCommand(["gnt-network", "remove", network2])

  AssertCommand(["gnt-network", "disconnect", network1, group1])
  # This should only produce a warning.
  AssertCommand(["gnt-network", "disconnect", network1])

  instance1 = GetInstance()
  # TODO: add conflicting image.
  LaunchInstance(instance1, ip=IP_IN_NET_2)
  # Conflicting IPs
  AssertCommand(["gnt-network", "connect", network2, defmode, deflink],
                fail=True)
  AssertCommand(["gnt-network", "connect", "--no-conflicts-check",
                 network2, defmode, deflink])
  AssertCommand(["gnt-network", "disconnect", network2])


def TestInstanceAddAndNetAdd():
  """ gnt-istance add / gnt-instance modify --net -1:add """
  (network1, network2, network3) = qa_utils.GetNonexistentNetworks(3)
  defmode, deflink = GetNicParams()

  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1,
                 "--gateway", GW_IN_NET_1, "--mac-prefix", "aa:bb:cc",
                 "--add-reserved-ips", IP_IN_NET_1,
                 "--network6", TEST_NET6_1,
                 "--gateway6", GW_IN_NET6_1, network1])
  AssertCommand(["gnt-network", "connect", network1, defmode, deflink])

  AssertCommand(["gnt-network", "add", "--network", TEST_NET_2, network2])
  AssertCommand(["gnt-network", "connect", network2, "routed", "rt5000"])

  AssertCommand(["gnt-network", "add", network3])
  AssertCommand(["gnt-network", "connect", network3, "routed", "rt100"])

  # (mac, ip, network, mode, link)
  success_cases = [
    (None, None, None, None, None),  # random mac and default nicparams
    ("generate", IP_IN_NET_3, None, "routed", "rt5000"), # given params
    (None, "pool", network1, None, None), # first IP in network given
    # TODO: include this use case with --no-conflicts-check
    #       just add an extra field in Launch|ModifyInstance
    #(None, "192.168.1.6", None, None, None), # IP but no net
    (None, None, network1, None, None), # nicparams/mac  inherited by network
    ]

  for (mac, ip, network, mode, link) in success_cases:
    instance1 = GetInstance()
    LaunchInstance(instance1, mac, ip, network, mode, link)
    ModifyInstance(instance1, idx=-1, action="add", mac=mac,
                   ip=ip, network=network, mode=mode, link=link)
    ModifyInstance(instance1, idx=1, action="remove")
    RemoveInstance(instance1)

  # test _AllIPs()
  instance1 = qa_config.AcquireInstance()
  LaunchInstance(instance1, ip="10.10.10.10")
  # this results to "Configuration data not consistent
  ModifyInstance(instance1, idx=-1, action="add", ip="10.10.10.10")
  ModifyInstance(instance1, idx=-1, action="add",
                 ip="10.10.10.10", network=network3)
  # this raises Corrupt configuration data
  ModifyInstance(instance1, idx=-1, action="add",
                 ip="10.10.10.10", network=network3, fail=True)
  RemoveInstance(instance1)

  fail_cases = [
    (None, None, None, "lala", None),
    (None, "lala", None, None, None),
    (None, None, "lala", None, None),
    (None, IP_IN_NET_2, None, None, None), # conflicting IP
    (None, None, None, "routed", None), # routed with no IP
    (None, "pool", network1, "routed", None), # nicparams along with network
    (None, "pool", network1, None, deflink),
   ]

  instance1 = GetInstance()
  instance2 = GetInstance()
  LaunchInstance(instance2)
  for (mac, ip, network, mode, link) in fail_cases:
    LaunchInstance(instance1, mac=mac, ip=ip, network=network,
                   mode=mode, link=link, fail=True)
    ModifyInstance(instance2, idx=-1, action="add", mac=mac,
                  ip=ip, network=network, mode=mode, link=link, fail=True)
    ModifyInstance(instance2, idx=0, action="modify", mac=mac,
                  ip=ip, network=network, mode=mode, link=link, fail=True)

  RemoveInstance(instance2)
  AssertCommand(["gnt-network", "disconnect", network1])
  AssertCommand(["gnt-network", "remove", network1])
  AssertCommand(["gnt-network", "disconnect", network2])
  AssertCommand(["gnt-network", "remove", network2])
  AssertCommand(["gnt-network", "disconnect", network3])
  AssertCommand(["gnt-network", "remove", network3])


def TestInstanceNetMod():
  """ gnt-istance modify --net 0:modify """
  (network1, network2) = qa_utils.GetNonexistentNetworks(2)
  defmode, deflink = GetNicParams()

  AssertCommand(["gnt-network", "add", "--network", TEST_NET_1,
                 "--gateway", GW_IN_NET_1, "--mac-prefix", "aa:bb:cc",
                 "--add-reserved-ips", IP_IN_NET_1,
                 "--network6", TEST_NET6_1,
                 "--gateway6", GW_IN_NET6_1, network1])
  AssertCommand(["gnt-network", "connect", network1, defmode, deflink])

  success_cases = [
    ("generate", IP_IN_NET_3, None, "routed", "rt5000"), # given params
    (None, "pool", network1, None, None), # first IP in network given
    (None, "none", "none", None, None),  # random mac and default nicparams
    (None, IP2_IN_NET_1, network1, None, None), # IP inside network
    #TODO: include this use case with --no-conflickts-check
    #(None, IP2_IN_NET_1, None, None, None), # IP but no net
    (None, None, network1, None, None), # nicparams/mac  inherited by network
    ]

  instance1 = GetInstance()
  LaunchInstance(instance1)
  for (mac, ip, network, mode, link) in success_cases:
    ModifyInstance(instance1, idx=0, action="modify", mac=mac,
                  ip=ip, network=network, mode=mode, link=link)
    # reset to defaults
    ModifyInstance(instance1, idx=0, action="modify", mac="generate",
                   ip="none", network="none", mode=defmode, link=deflink)

  AssertCommand(["gnt-network", "add", "--network", TEST_NET_2, network2])
  AssertCommand(["gnt-network", "connect", network2, "routed", "rt5000"])
  # put instance inside network1
  ModifyInstance(instance1, idx=0, action="modify", ip="pool", network=network1)
  # move instance to network2
  ModifyInstance(instance1, idx=0, action="modify", ip="pool", network=network2)

  RemoveInstance(instance1)
  AssertCommand(["gnt-network", "disconnect", network1])
  AssertCommand(["gnt-network", "remove", network1])
  AssertCommand(["gnt-network", "disconnect", network2])
  AssertCommand(["gnt-network", "remove", network2])
