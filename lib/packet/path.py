# Copyright 2014 ETH Zurich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
:mod:`path` --- SCION Path packets
==================================
"""
# Stdlib
import copy

# SCION
from lib.defines import SCION_MIN_MTU
from lib.packet.opaque_field import (
    HopOpaqueField,
    InfoOpaqueField,
    OpaqueField,
    OpaqueFieldList,
)
from lib.packet.packet_base import Serializable
from lib.packet.pcb_ext.mtu import MtuPcbExt
from lib.util import Raw


class SCIONPath(Serializable):
    NAME = "SCIONPath"
    A_IOF = "A_segment_iof"
    A_HOFS = "A_segment_hofs"
    B_IOF = "B_segment_iof"
    B_HOFS = "B_segment_hofs"
    C_IOF = "C_segment_iof"
    C_HOFS = "C_segment_hofs"
    OF_ORDER = A_IOF, A_HOFS, B_IOF, B_HOFS, C_IOF, C_HOFS
    IOF_LABELS = A_IOF, B_IOF, C_IOF
    HOF_LABELS = A_HOFS, B_HOFS, C_HOFS

    def __init__(self, raw=None):  # pragma: no cover
        self._ofs = OpaqueFieldList(self.OF_ORDER)
        self._iof_idx = None
        self._hof_idx = None
        self.interfaces = []
        self.mtu = 0
        super().__init__(raw)

    def _parse(self, raw):
        data = Raw(raw, self.NAME)
        if data:
            # Parse first segment
            a_iof = self._parse_iof(data, self.A_IOF)
            self._parse_hofs(data, self.A_HOFS, a_iof.hops)
        if data:
            # Parse second segment
            b_iof = self._parse_iof(data, self.B_IOF)
            self._parse_hofs(data, self.B_HOFS, b_iof.hops)
        if data:
            # Parse third segment
            assert not a_iof.shortcut
            c_iof = self._parse_iof(data, self.C_IOF)
            self._parse_hofs(data, self.C_HOFS, c_iof.hops)
        self._init_of_idxs()

    def _parse_iof(self, data, label):
        """
        Parse a raw :any:`InfoOpaqueField`.

        :param Raw data: Raw instance.
        :param str label: OF label.
        """
        iof = InfoOpaqueField(data.pop(InfoOpaqueField.LEN))
        self._ofs.set(label, [iof])
        return iof

    def _parse_hofs(self, data, label, count):
        """
        Parse raw :any:`HopOpaqueFields`\s.

        :param Raw data: Raw instance.
        :param str label: OF label.
        :param int count: Number of HOFs to parse.
        """
        hofs = []
        for _ in range(count):
            hofs.append(HopOpaqueField(data.pop(HopOpaqueField.LEN)))
        self._ofs.set(label, hofs)

    @classmethod
    def from_values(cls, a_iof=None, a_hofs=None, b_iof=None,
                    b_hofs=None, c_iof=None, c_hofs=None):  # pragma: no cover
        inst = cls()
        inst._set_ofs(inst.A_IOF, a_iof)
        inst._set_ofs(inst.A_HOFS, a_hofs)
        inst._set_ofs(inst.B_IOF, b_iof)
        inst._set_ofs(inst.B_HOFS, b_hofs)
        inst._set_ofs(inst.C_IOF, c_iof)
        inst._set_ofs(inst.C_HOFS, c_hofs)
        inst._init_of_idxs()
        return inst

    def pack(self):  # pragma: no cover
        raw = self._ofs.pack()
        assert len(raw) == len(self)
        return raw

    def _set_ofs(self, label, value):
        """
        Set an OF label to the given value.

        :param str label: The OF label.
        :param value:
            Can be ``None``, a single Opaque Field, or a list of Opaque Fields.
        """
        if value is None:
            data = []
        elif isinstance(value, list):
            data = value
        else:
            data = [value]
        self._ofs.set(label, data)

    def _init_of_idxs(self):
        self._iof_idx = 0
        self._hof_idx = 0
        if not len(self._ofs):
            return
        iof = self.get_iof()
        if iof.peer:
            hof = self._ofs.get_by_idx(1)
            if hof.xover:
                self._hof_idx += 1
        self.inc_hof_idx()

    def get_of_idxs(self):  # pragma: no cover
        """
        Get current InfoOpaqueField and HopOpaqueField indexes.

        :return: Tuple (int, int) of IOF index and HOF index, respectively.
        """
        return self._iof_idx, self._hof_idx

    def set_of_idxs(self, iof_idx, hof_idx):  # pragma: no cover
        """Set current InfoOpaqueField and HopOpaqueField indexes."""
        self._iof_idx = iof_idx
        self._hof_idx = hof_idx

    def reverse(self):
        """Reverse the direction of the path."""
        if not len(self._ofs):
            # Empty path doesn't need reversal.
            return
        iof_label = self._ofs.get_label_by_idx(self._iof_idx)
        swap_iof, swap_hof = None, None
        # Determine which IOF/HOFs need to be swapped, if any.
        if self._ofs.count(self.C_IOF):
            swap_iof, swap_hof = self.C_IOF, self.C_HOFS
        elif self._ofs.count(self.B_IOF):
            swap_iof, swap_hof = self.B_IOF, self.B_HOFS
        # Do the swap as needed.
        if swap_iof:
            self._ofs.swap(self.A_IOF, swap_iof)
            self._ofs.swap(self.A_HOFS, swap_hof)
        # Reverse IOF flags.
        for label in self.IOF_LABELS:
            self._ofs.reverse_up_flag(label)
        # Reverse HOF lists.
        for label in self.HOF_LABELS:
            self._ofs.reverse_label(label)
        # Update IOF index:
        # - (1) For paths with a single segment, just get the index of the
        #   original label.
        # - (2) For paths with 2 segments, get the index of the opposite label.
        # - (3) For paths with 3 segments, if the initial label was at either
        #   end, use (2), otherwise use (1), as the current label didn't get
        #   swapped.
        if swap_iof and iof_label == self.A_IOF:
            iof_idx = self._ofs.get_idx_by_label(swap_iof)
        elif swap_iof and iof_label == swap_iof:
            iof_idx = self._ofs.get_idx_by_label(self.A_IOF)
        else:
            iof_idx = self._ofs.get_idx_by_label(iof_label)
        # Update the HOF index by simply subtracting it from the total number of
        # OFs.
        self.set_of_idxs(iof_idx, len(self._ofs) - self._hof_idx)

    def get_hof_ver(self, ingress=True):
        """Return the :any:`HopOpaqueField` needed to verify the current HOF."""
        iof = self.get_iof()
        hof = self.get_hof()
        if not hof.xover or (iof.shortcut and not iof.peer):
            # For normal hops on any type of segment, or cross-over hops on
            # non-peer shortcut hops, just use next/prev HOF.
            return self._get_hof_ver_normal(iof)
        if iof.peer:
            # Peer shortcut paths have two extra HOFs; 1 for the peering
            # interface, and another from the upstream interface, used for
            # verification only.
            ingress_up = {(True, True): +2, (True, False): +1,
                          (False, True): -1, (False, False): -2}
        else:
            # Non-peer shortcut paths have an extra HOF above the last hop, used
            # for verification of the last hop in that segment.
            ingress_up = {(True, True): None, (True, False): -1,
                          (False, True): +1, (False, False): None}
        # Map the local direction of travel and the IOF up flag to the required
        # offset of the verification HOF (or None, if there's no relevant HOF).
        offset = ingress_up[ingress, iof.up_flag]
        if offset is None:
            return None
        return self._ofs.get_by_idx(self._hof_idx + offset)

    def _get_hof_ver_normal(self, iof):
        # If this is the last hop of an Up path, or the first hop of a Down
        # path, there's no previous HOF to verify against.
        if (iof.up_flag and self._hof_idx == self._iof_idx + iof.hops) or (
                not iof.up_flag and self._hof_idx == self._iof_idx + 1):
            return None
        # Otherwise use the next/prev HOF based on the up flag.
        offset = 1 if iof.up_flag else -1
        return self._ofs.get_by_idx(self._hof_idx + offset)

    def get_iof(self):  # pragma: no cover
        """Get current :any:`InfoOpaqueField`."""
        if self._iof_idx is None:
            return None
        return self._ofs.get_by_idx(self._iof_idx)

    def get_hof(self):  # pragma: no cover
        """Get current :any:`HopOpaqueField`."""
        if self._hof_idx is None:
            return None
        return self._ofs.get_by_idx(self._hof_idx)

    def inc_hof_idx(self):
        """
        Increment the HOF idx to next routing HOF.

        Skip VERIFY_ONLY HOFs, as they are not used for routing.
        Also detect when there are no HOFs left in the current segment, and
        switch to the next segment, before restarting.
        """
        iof = self.get_iof()
        while True:
            self._hof_idx += 1
            if (self._hof_idx - self._iof_idx) > iof.hops:
                # Switch to the next segment
                self._iof_idx = self._hof_idx
                iof = self.get_iof()
                # Continue looking for a routing HOF
                continue
            hof = self.get_hof()
            if not hof.verify_only:
                break

    def get_fwd_if(self):  # pragma: no cover
        """Return the interface to forward the current packet to."""
        if not len(self._ofs):
            return 0
        iof = self.get_iof()
        hof = self.get_hof()
        if iof.up_flag:
            return hof.ingress_if
        return hof.egress_if

    def get_as_hops(self):
        total = 0
        segs = 0
        peer = False
        for l in self.IOF_LABELS:
            res = self._ofs.get_by_label(l)
            if not res:
                break
            peer |= res[0].peer
            total += self._get_as_hops(res[0])
            segs += 1
        if not peer:
            total -= segs - 1
        return total

    def _get_as_hops(self, iof):  # pragma: no cover
        if not iof.shortcut:
            return iof.hops
        if not iof.peer:
            return iof.hops - 1
        return iof.hops - 2

    def __len__(self):  # pragma: no cover
        """Return the path length in bytes."""
        return len(self._ofs) * OpaqueField.LEN

    def __str__(self):
        s = []
        s.append("<SCION-Path>")

        for name, iof_label, hofs_label in (
            ("A", self.A_IOF, self.A_HOFS), ("B", self.B_IOF, self.B_HOFS),
            ("C", self.C_IOF, self.C_HOFS),
        ):
            iof = self._ofs.get_by_label(iof_label)
            if not iof:
                break
            s.append("  <%s-Segment>" % name)
            s.append("    %s" % iof[0])
            for of in self._ofs.get_by_label(hofs_label):
                s.append("    %s" % of)
            s.append("  </%s-Segment>" % name)
        s.append("</SCION-Path>")
        return "\n".join(s)


def valid_mtu(mtu):
    """
    Check validity of mtu value
    We assume any SCION AS supports at least the IPv6 min MTU
    """
    return mtu and mtu >= SCION_MIN_MTU


def min_mtu(*candidates):
    """
    Return minimum of n mtu values, checking for validity
    """
    return min(filter(valid_mtu, candidates), default=0)


class PathCombinator(object):
    """
    Class that contains functions required to build end-to-end SCION paths.
    """
    @classmethod
    def build_shortcut_paths(cls, up_segments, down_segments):
        """
        Returns a list of all shortcut paths (peering and crossover paths) that
        can be built using the provided up- and down-segments.

        :param list up_segments: List of `up` :any:`PathSegment`\s.
        :param list down_segments: List of `down` :any:`PathSegment`\s.
        :returns: List of paths.
        """
        paths = []
        for up in up_segments:
            for down in down_segments:
                path = cls._build_shortcut_path(up, down)
                if path and path not in paths:
                    paths.append(path)
        return paths

    @classmethod
    def build_core_paths(cls, up_segment, down_segment, core_segments):
        """
        Returns list of all paths that can be built as combination of the
        supplied segments.

        :param list up_segments: List of `up` :any:`PathSegment`\s
        :param list core_segments: List of `core` :any:`PathSegment`\s
        :param list down_segments: List of `down` :any:`PathSegment`\s
        :returns: List of paths.
        """
        paths = []
        path = cls._build_core_path(up_segment, [], down_segment)
        if path:
            paths.append(path)
        if core_segments:
            for core_segment in core_segments:
                path = cls._build_core_path(up_segment, core_segment,
                                            down_segment)
                if path and path not in paths:
                    paths.append(path)
        return paths

    @classmethod
    def _build_shortcut_path(cls, up_segment, down_segment):
        """
        Takes :any:`PathSegment`\s and tries to combine them into short path via
        any cross-over or peer links found.

        :param list up_segment: `up` :any:`PathSegment`.
        :param list down_segment: `down` :any:`PathSegment`.
        :returns: SCIONPath if a shortcut path is found, otherwise ``None``.
        """
        # TODO check if stub ASs are the same...
        if (not up_segment or not down_segment or
                not up_segment.ases or not down_segment.ases):
            return None

        # looking for xovr and peer points
        xovr, peer = cls._get_xovr_peer(up_segment, down_segment)

        if not xovr and not peer:
            return None

        def _sum_pt(pt):
            if pt is None:
                return 0
            return sum(pt)

        if _sum_pt(peer) > _sum_pt(xovr):
            # Peer is best.
            return cls._join_shortcuts(up_segment, down_segment, peer, True)
        else:
            # Xovr is best
            return cls._join_shortcuts(up_segment, down_segment, xovr, False)

    @classmethod
    def _build_core_path(cls, up_segment, core_segment, down_segment):
        """
        Joins the supplied segments into a core fullpath.

        :param list up_segment: `up` :any:`PathSegment`.
        :param list core_segment:
            `core` :any:`PathSegment` (must have down-segment orientation), or
            ``None``.
        :param list down_segment: `down` :any:`PathSegment`.
        :returns: a SCIONPath if a path is found, otherwise None.
        """
        if (not up_segment or not down_segment or
                not up_segment.ases or not down_segment.ases):
            return None

        if not cls._check_connected(up_segment, core_segment, down_segment):
            return None

        up_iof, up_hofs, up_mtu = cls._copy_segment(
            up_segment, False, bool(core_segment or down_segment))
        core_iof, core_hofs, core_mtu = cls._copy_segment(
            core_segment, bool(up_segment), bool(down_segment))
        down_iof, down_hofs, down_mtu = cls._copy_segment(
            down_segment, bool(up_segment or core_segment), False, up=False)
        path = SCIONPath.from_values(up_iof, up_hofs, core_iof, core_hofs,
                                     down_iof, down_hofs)
        path.mtu = min_mtu(up_mtu, core_mtu, down_mtu)
        up_core = list(reversed(up_segment.ases))
        if core_segment:
            up_core += list(reversed(core_segment.ases))
        cls._add_interfaces(path, up_core)
        cls._add_interfaces(path, down_segment.ases, up=False)
        return path

    @classmethod
    def _add_interfaces(cls, path, segment_ases, up=True):
        """
        Add interface IDs of segment_ases to path. Order of IDs depends on up
        flag.
        """
        for block in segment_ases:
            isd_as = block.pcbm.isd_as
            egress = block.pcbm.hof.egress_if
            ingress = block.pcbm.hof.ingress_if
            if up:
                if egress:
                    path.interfaces.append((isd_as, egress))
                if ingress:
                    path.interfaces.append((isd_as, ingress))
            else:
                if ingress:
                    path.interfaces.append((isd_as, ingress))
                if egress:
                    path.interfaces.append((isd_as, egress))

    @classmethod
    def _copy_segment(cls, segment, xover_start, xover_end, up=True):
        """
        Copy a :any:`PathSegment`, setting the up flag, the crossover point
        flags, and optionally reversing the hops.
        """
        if not segment:
            return None, None, None
        iof = copy.deepcopy(segment.iof)
        iof.up_flag = up
        hofs, mtu = cls._copy_hofs(segment.ases, reverse=up)
        if xover_start:
            hofs[0].xover = True
        if xover_end:
            hofs[-1].xover = True
        return iof, hofs, mtu

    @classmethod
    def _get_xovr_peer(cls, up_segment, down_segment):
        """
        Find the shortest xovr (preferred) and peer points between the supplied
        segments.

        *Note*: 'shortest' is calculated by looking for the point that's
        furthest from the core.

        :param list up_segment: `up` :any:`PathSegment`.
        :param list down_segment: `down` :any:`PathSegment`.
        :returns:
            Tuple of the shortest xovr and peer points.
        """
        xovrs = []
        peers = []
        for up_i, up_as in enumerate(up_segment.ases[1:], 1):
            for down_i, down_as in enumerate(down_segment.ases[1:], 1):
                if up_as.pcbm.isd_as == down_as.pcbm.isd_as:
                    xovrs.append((up_i, down_i))
                    continue
                for up_peer in up_as.pms:
                    for down_peer in down_as.pms:
                        if (up_peer.isd_as == down_as.pcbm.isd_as and
                                down_peer.isd_as == up_as.pcbm.isd_as):
                            peers.append((up_i, down_i))
        xovr = peer = None
        if xovrs:
            xovr = max(xovrs, key=lambda tup: sum(tup))
        if peers:
            peer = max(peers, key=lambda tup: sum(tup))
        return xovr, peer

    @classmethod
    def _join_shortcuts(cls, up_segment, down_segment, point, peer=True):
        """
        Joins the supplied segments into a shortcut fullpath.

        :param list up_segment: `up` :any:`PathSegment`.
        :param list down_segment: `down` :any:`PathSegment`.
        :param tuple point: Indexes of peer/xovr point.
        :param bool peer:
            ``True`` if the shortcut uses a peering link, ``False`` if it uses a
            cross-over link
        :returns:
            :any:`PeerPath` if using a peering link, otherwise
            :any:`CrossOverPath`.
        """
        (up_index, down_index) = point

        up_iof, up_hofs, up_upstream_hof, up_mtu = \
            cls._copy_segment_shortcut(up_segment, up_index)
        down_iof, down_hofs, down_upstream_hof, down_mtu = \
            cls._copy_segment_shortcut(down_segment, down_index, up=False)

        up_iof.shortcut = down_iof.shortcut = True
        if not peer:
            # It's a cross-over path.
            up_iof.peer = down_iof.peer = False
            up_hofs.append(up_upstream_hof)
            down_hofs.insert(0, down_upstream_hof)
        else:
            # It's a peer path.
            up_iof.peer = down_iof.peer = True
            up_peering_hof, down_peering_hof = cls._join_shortcuts_peer(
                up_segment.ases[up_index], down_segment.ases[down_index])
            up_hofs.extend([up_peering_hof, up_upstream_hof])
            down_hofs.insert(0, down_peering_hof)
            down_hofs.insert(0, down_upstream_hof)
        args = []
        for iof, hofs in [(up_iof, up_hofs), (down_iof, down_hofs)]:
            l = len(hofs)
            # Any shortcut path with 2 HOFs is redundant, and can be dropped.
            if l > 2:
                iof.hops = l
                args.extend([iof, hofs])
        path = SCIONPath.from_values(*args)
        for i in reversed(range(up_index, len(up_segment.ases))):
            pcbm = up_segment.ases[i].pcbm
            egress = pcbm.hof.egress_if
            ingress = pcbm.hof.ingress_if
            if egress:
                path.interfaces.append((pcbm.isd_as, egress))
            if i != up_index:
                path.interfaces.append((pcbm.isd_as, ingress))
        if peer:
            up_pcbm = up_segment.ases[up_index].pcbm
            down_pcbm = down_segment.ases[down_index].pcbm
            path.interfaces.append((up_pcbm.isd_as, up_peering_hof.ingress_if))
            path.interfaces.append((
                down_pcbm.isd_as, down_peering_hof.ingress_if))
        for i in range(down_index, len(down_segment.ases)):
            pcbm = down_segment.ases[i].pcbm
            egress = pcbm.hof.egress_if
            ingress = pcbm.hof.ingress_if
            if i != down_index:
                path.interfaces.append((pcbm.isd_as, ingress))
            if egress:
                path.interfaces.append((pcbm.isd_as, egress))
        path.mtu = min_mtu(up_mtu, down_mtu)
        return path

    @classmethod
    def _check_connected(cls, up_segment, core_segment, down_segment):
        """
        Check if the supplied segments are connected in sequence. If the `core`
        segment is not specified, it is ignored.
        """
        up_first_ia = up_segment.get_first_pcbm().isd_as
        down_first_ia = down_segment.get_first_pcbm().isd_as
        if core_segment:
            core_first_ia = core_segment.get_first_pcbm().isd_as
            core_last_ia = core_segment.get_last_pcbm().isd_as
            if (core_last_ia != up_first_ia or core_first_ia != down_first_ia):
                return False
        elif up_first_ia != down_first_ia:
            return False
        return True

    @classmethod
    def _copy_hofs(cls, ases, reverse=True):
        """
        Copy :any:`HopOpaqueField`\s, and optionally reverse the result.

        :param list ases: List of :any:`ASMarking` objects.
        :param bool reverse: If ``True``, reverse the list before returning it.
        :returns:
            List of copied :any:`HopOpaqueField`\s.
        """
        hofs = []
        mtu = None
        for block in ases:
            for ext in block.ext:
                if ext.EXT_TYPE == MtuPcbExt.EXT_TYPE:
                    mtu = min_mtu(mtu, ext.mtu)
            hofs.append(copy.deepcopy(block.pcbm.hof))
        if reverse:
            hofs.reverse()
        return hofs, mtu

    @classmethod
    def _copy_segment_shortcut(cls, segment, index, up=True):
        """
        Copy a segment for a path shortcut, extracting the upstream
        :any:`HopOpaqueField`, and setting the `up` flag and HOF types
        appropriately.

        :param PathSegment segment: Segment to copy.
        :param int index: Index at which to start the copy.
        :param bool up:
            ``True`` if the path direction is `up` (which will reverse the
            segment direction), ``False`` otherwise (which will leave the
            segment direction unchanged).
        :returns:
            The copied :any:`InfoOpaqueField`, path :any:`HopOpaqueField`\s and
            Upstream :any:`HopOpaqueField`.
        """
        iof = copy.deepcopy(segment.iof)
        iof.hops -= index
        iof.up_flag = up
        # Copy segment HOFs
        ases = segment.ases[index:]
        hofs, mtu = cls._copy_hofs(ases, reverse=up)
        xovr_idx = -1 if up else 0
        hofs[xovr_idx].xover = True
        # Extract upstream HOF
        upstream_hof = copy.deepcopy(segment.ases[index - 1].pcbm.hof)
        upstream_hof.xover = False
        upstream_hof.verify_only = True
        return iof, hofs, upstream_hof, mtu

    @classmethod
    def _join_shortcuts_peer(cls, up_as, down_as):
        """
        Finds the peering :any:`HopOpaqueField` of the shortcut path.
        """
        # FIXME(kormat): Is it possible for there to be multiple matches? Could
        # 2 ASs have >1 peering link to the other?
        for up_peer in up_as.pms:
            for down_peer in down_as.pms:
                if (up_peer.isd_as == down_as.pcbm.isd_as and
                        down_peer.isd_as == up_as.pcbm.isd_as):
                    return up_peer.hof, down_peer.hof

    @classmethod
    def tuples_to_full_paths(cls, tuples):
        """
        For a set of tuples of possible end-to-end path [format is:
        (up_seg, core_seg, down_seg)], return a list of fullpaths.

        """
        # TODO(PSz): eventually this should replace _build_core_paths.
        res = []
        for up_segment, core_segment, down_segment in tuples:
            if not up_segment and not core_segment and not down_segment:
                continue

            up_iof, up_hofs, up_mtu = cls._copy_segment(
                up_segment, False, (core_segment or down_segment))
            core_iof, core_hofs, core_mtu = cls._copy_segment(
                core_segment, up_segment, down_segment)
            down_iof, down_hofs, down_mtu = cls._copy_segment(
                down_segment, (up_segment or core_segment), False, up=False)
            args = []
            for iof, hofs in [(up_iof, up_hofs), (core_iof, core_hofs),
                              (down_iof, down_hofs)]:
                if iof:
                    args.extend([iof, hofs])
            path = SCIONPath.from_values(*args)
            path.mtu = min_mtu(up_mtu, core_mtu, down_mtu)
            if up_segment:
                up_core = list(reversed(up_segment.ases))
            else:
                up_core = []
            if core_segment:
                up_core += list(reversed(core_segment.ases))
            cls._add_interfaces(path, up_core)
            if down_segment:
                down_core = down_segment.ases
            else:
                down_core = []
            cls._add_interfaces(path, down_core, up=False)
            res.append(path)
        return res


def parse_path(raw):  # pragma: no cover
    return SCIONPath(raw)
