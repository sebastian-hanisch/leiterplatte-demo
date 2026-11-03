"""Verlegeraster: zwei Lagen, Pads als Durchsteckpads auf beiden Lagen, Gehäuse sperren nur die Oberseite. Knoten = Schicht * (W * H) + y * W + x."""

from dataclasses import dataclass

from lpl_scenario import Instance, body_cells, pin_xy

FREE = -1        # frei
BODY = -2        # Gehäuseinneres (nur Schicht 0)
NC_PAD = -3      # Pad ohne Netz: gesperrt für alle
# Werte >= 0 in `fixed`: Pad dieses Netzes; nur das Netz selbst darf hindurch


@dataclass(frozen=True)
class Board:
    width: int
    height: int
    fixed: tuple   # je Knoten FREE, BODY, NC_PAD oder Netznummer
    pads: tuple    # je Netz die Zellen (y * W + x) seiner Pads

    @property
    def cells(self) -> int:
        return self.width * self.height

    @property
    def nodes(self) -> int:
        return 2 * self.cells


def build_board(inst: Instance, poses: list) -> Board:
    """Raster aus Instanz und Lagen: Gehäuse sperren Schicht 0, Pads gehören ihrem Netz (beide Schichten), Pads ohne Netz sind gesperrt."""
    w, h = inst.width, inst.height
    hw = w * h
    fixed = [FREE] * (2 * hw)
    pin_net = {(ci, pi): k for k, net in enumerate(inst.nets) for ci, pi in net}
    for ci, fp in enumerate(inst.comps):
        for x, y in body_cells(fp, poses[ci]):
            fixed[y * w + x] = BODY
        for pi in range(len(fp.pins)):
            x, y = pin_xy(fp, poses[ci], pi)
            value = pin_net.get((ci, pi), NC_PAD)
            fixed[y * w + x] = value
            fixed[hw + y * w + x] = value
    pads = tuple(tuple(pin_xy(inst.comps[ci], poses[ci], pi)[1] * w + pin_xy(inst.comps[ci], poses[ci], pi)[0] for ci, pi in net) for net in inst.nets)
    return Board(w, h, tuple(fixed), pads)


def cell_of(board: Board, node: int) -> tuple[int, int, int]:
    """(x, y, Schicht) eines Knotens."""
    layer, r = divmod(node, board.cells)
    y, x = divmod(r, board.width)
    return x, y, layer
