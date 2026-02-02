"""
PROJECT: JEB - JADNET Electronics Box - INDUSTRIAL SATELLITE (SLAVE)
VERSION: 0.1 - 2024-06-05
TYPE: "01" (Industrial)

--- TODO ---
Implement power monitoring via ADC.
Implement power protection for downstream satellites.
Optimize async tasks for responsiveness.
Implement configuration commands from Master.
UART Buffering and flow control.
Test with multiple chained satellites.
"""

import asyncio

from managers import SatManager

MY_TYPE = "01"  # Industrial Satellite
sat = SatManager(MY_TYPE)

asyncio.run(sat.start())
