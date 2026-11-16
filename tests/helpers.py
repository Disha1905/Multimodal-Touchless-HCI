def hand(thumb=0, index=0, middle=0, ring=0, pinky=0):
    """Synthetic upright hand: 21 (x, y, z) landmarks encoding finger states."""
    lm = [(0.5, 0.9, 0)] * 21
    lm = list(lm)
    lm[0] = (0.5, 0.9, 0)
    lm[5] = (0.45, 0.6, 0)      # index MCP
    lm[17] = (0.6, 0.65, 0)     # pinky MCP
    lm[3] = (0.40, 0.65, 0)     # thumb IP
    lm[4] = (0.25, 0.60, 0) if thumb else (0.46, 0.64, 0)   # thumb tip (out vs tucked)
    for tip, pip, mcpx, up in ((8, 6, 0.45, index), (12, 10, 0.5, middle),
                               (16, 14, 0.55, ring), (20, 18, 0.6, pinky)):
        lm[pip] = (mcpx, 0.5, 0)
        lm[tip] = (mcpx, 0.3 if up else 0.62, 0)
    return lm
