#
#

# Copyright (C) 2011, 2012 Google Inc.
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


"""IP address pool management functions.

"""

import ipaddr

from bitarray import bitarray

from ganeti import errors
from ganeti import utils
from ganeti import constants


def _ComputeIpv4NumHosts(network_size):
  """Derives the number of hosts in an IPv4 network from the size.

  """
  return 2 ** (32 - network_size)


IPV4_NETWORK_MIN_SIZE = 30
# FIXME: This limit is for performance reasons. Remove when refactoring
# for performance tuning was successful.
IPV4_NETWORK_MAX_SIZE = 16
IPV4_NETWORK_MIN_NUM_HOSTS = _ComputeIpv4NumHosts(IPV4_NETWORK_MIN_SIZE)
IPV4_NETWORK_MAX_NUM_HOSTS = _ComputeIpv4NumHosts(IPV4_NETWORK_MAX_SIZE)


class Network(object):
  """ Wrapper Class for networks.

  Used to get a network out of a L{objects.Network}. In case nobj
  has an IPv4 subnet it returns an AddressPool object. Otherwise
  a GenericNetwork object is created. To get a network use:
  network.Network(nobj)

  """
  def __new__(cls, nobj):
    if nobj.network:
      return AddressPool(nobj)
    else:
      return GenericNetwork(nobj)

  @classmethod
  def Check(cls, address, network):
    try:
      if network:
        network = ipaddr.IPNetwork(network)
      if address:
        address = ipaddr.IPAddress(address)
    except ValueError, e:
      raise errors.OpPrereqError(e, errors.ECODE_INVAL)

    if address and not network:
      raise errors.OpPrereqError("Address '%s' but no network." % address,
                                 errors.ECODE_INVAL)
    if address and address not in network:
      raise errors.OpPrereqError("Address '%s' not in network '%s'." %
                                 (address, network),
                                 errors.ECODE_INVAL)


class GenericNetwork(object):
  """ Base class for networks.

  This includes all info and methods deriving from subnets and gateways
  both IPv4 and IPv6. Implements basic checks and abstracts the methods
  that are invoked by external methods.

  """
  def __init__(self, nobj):
    """Initializes a Generic Network from an L{objects.Network} object.

    @type nobj: L{objects.Network}
    @param nobj: the network object

    """
    self.network = None
    self.gateway = None
    self.network6 = None
    self.gateway6 = None

    self.nobj = nobj

    if self.nobj.gateway and not self.nobj.network:
      raise errors.OpPrereqError("Gateway without network. Cannot proceed")

    if self.nobj.network:
      self.network = ipaddr.IPNetwork(self.nobj.network)
      if self.nobj.gateway:
        self.gateway = ipaddr.IPAddress(self.nobj.gateway)
        if self.gateway not in self.network:
          raise errors.OpPrereqError("Gateway not in network.",
                                     errors.ECODE_INVAL)

    if self.nobj.gateway6 and not self.nobj.network6:
      raise errors.OpPrereqError("IPv6 Gateway without IPv6 network."
                                 " Cannot proceed.",
                                 errors.ECODE_INVAL)
    if self.nobj.network6:
      self.network6 = ipaddr.IPv6Network(self.nobj.network6)
      if self.nobj.gateway6:
        self.gateway6 = ipaddr.IPv6Address(self.nobj.gateway6)
        if self.gateway6 not in self.network6:
          raise errors.OpPrereqError("IPv6 Gateway not in IPv6 network.",
                                     errors.ECODE_INVAL)

  def _Validate(self):
    if self.gateway:
      assert self.network
      assert self.gateway in self.network
    if self.gateway6:
      assert self.network6
      assert self.gateway6 in self.network6 or self.gateway6.is_link_local

  def Contains(self, address):
    addr = ipaddr.IPAddress(address)
    if addr.version == constants.IP4_VERSION and self.network:
      return addr in self.network
    elif addr.version == constants.IP6_VERSION and self.network6:
      return addr in self.network6

  def IsReserved(self, address):
    raise NotImplementedError

  def Reserve(self, address, external):
    raise NotImplementedError

  def Release(self, address, external):
    raise NotImplementedError

  def GenerateFree(self):
    raise NotImplementedError

  def GetStats(self):
    return {}


class AddressPool(GenericNetwork):
  """Address pool class, wrapping an C{objects.Network} object.

  This class provides methods to manipulate address pools, backed by
  L{objects.Network} objects.

  """
  FREE = bitarray("0")
  RESERVED = bitarray("1")

  def __init__(self, nobj):
    """Initialize a new IPv4 address pool from an L{objects.Network} object.

    @type network: L{objects.Network}
    @param network: the network object from which the pool will be generated

    """
    super(AddressPool, self).__init__(nobj)
    if self.nobj.reservations and self.nobj.ext_reservations:
      self.reservations = bitarray(self.nobj.reservations)
      self.ext_reservations = bitarray(self.nobj.ext_reservations)
    else:
      self._InitializeReservations()

    self._Validate()

  def _InitializeReservations(self):
    self.reservations = bitarray(self.network.numhosts)
    self.reservations.setall(False) # pylint: disable=E1103

    self.ext_reservations = bitarray(self.network.numhosts)
    self.ext_reservations.setall(False) # pylint: disable=E1103

    for ip in [self.network[0], self.network[-1]]:
      self.Reserve(ip, external=True)

    if self.nobj.gateway:
      self.Reserve(self.nobj.gateway, external=True)

    self._Update()

  def _GetAddrIndex(self, address):
    addr = ipaddr.IPAddress(address)
    assert addr in self.network
    return int(addr) - int(self.network.network)

  def _Update(self):
    """Write address pools back to the network object.

    """
    # pylint: disable=E1103
    self.net.ext_reservations = self.ext_reservations.to01()
    self.net.reservations = self.reservations.to01()

  def _Mark(self, address, value=True, external=False):
    idx = self._GetAddrIndex(address)
    if external:
      self.ext_reservations[idx] = value
    else:
      self.reservations[idx] = value
    self._Update()

  def _GetSize(self):
    return 2 ** (32 - self.network.prefixlen)

  @property
  def _all_reservations(self):
    """Return a combined map of internal and external reservations.

    """
    return (self.reservations | self.ext_reservations)

  def IsFull(self):
    """Check whether the network is full.

    """
    return self.all_reservations.all()

  def _Validate(self):
    super(AddressPool, self)._Validate()
    assert len(self.reservations) == self.network.numhosts
    assert len(self.ext_reservations) == self.network.numhosts
    all_res = self.reservations & self.ext_reservations
    assert not all_res.any()

  def _GetReservedCount(self):
    """Get the count of reserved addresses.

    """
    return self._all_reservations.count(True)

  def _GetFreeCount(self):
    """Get the count of unused addresses.

    """
    return self._all_reservations.count(False)

  def _GetMap(self):
    """Return a textual representation of the network's occupation status.

    """
    return self._all_reservations.to01().replace("1", "X").replace("0", ".")

  def _GetExternalReservations(self):
    """Returns a list of all externally reserved addresses.

    """
    # pylint: disable=E1103
    idxs = self.ext_reservations.search(self.RESERVED)
    return [str(self.network[idx]) for idx in idxs]

  def IsReserved(self, address, external=False):
    """Checks if the given IP is reserved.

    """
    idx = self._GetAddrIndex(address)
    if external:
      return self.ext_reservations[idx]
    else:
      return self.reservations[idx]

  def Reserve(self, address, external=False):
    """Mark an address as used.

    """
    if self.IsReserved(address, external):
      if external:
        msg = "IP %s is already externally reserved" % address
      else:
        msg = "IP %s is already used by an instance" % address
      raise errors.AddressPoolError(msg)

    self._Mark(address, external=external)

  def Release(self, address, external=False):
    """Release a given address reservation.

    """
    if not self.IsReserved(address, external):
      if external:
        msg = "IP %s is not externally reserved" % address
      else:
        msg = "IP %s is not used by an instance" % address
      raise errors.AddressPoolError(msg)

    self._Mark(address, value=False, external=external)

  def GetFreeAddress(self):
    """Returns the first available address.

    """
    if self.IsFull():
      raise errors.AddressPoolError("%s is full" % self.network)

    idx = self.all_reservations.index(False)
    address = str(self.network[idx])
    self.Reserve(address)
    return address

  def GenerateFree(self):
    """Returns the first free address of the network.

    @raise errors.AddressPoolError: Pool is full

    """
    idx = self._all_reservations.search(self.FREE, 1)
    if not idx:
      raise errors.NetworkError("%s is full" % self.network)
    return str(self.network[idx[0]])

  def GetStats(self):
    """Returns statistics for a network address pool.

    """
    return {
      "free_count": self._GetFreeCount(),
      "reserved_count": self._GetReservedCount(),
      "map": self._GetMap(),
      "external_reservations":
        utils.CommaJoin(self._GetExternalReservations()),
      }
