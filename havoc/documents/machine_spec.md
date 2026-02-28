# Machine Specification — Sorting Station 7

## Equipment Details
- Machine ID: SORT-STN-007
- Robot Model: Dobot CR S0-100
- Controller: TCP/IP Dashboard v3.5

## Operating Parameters

| Parameter          | Value | Unit | Limit Type |
|--------------------|-------|------|------------|
| Max Speed          | 70    | %    | Upper      |
| Max Grip Force     | 12    | N    | Upper      |
| Max Acceleration   | 50    | %    | Upper      |
| Min Clearance      | 25    | mm   | Lower      |
| Operating Temp     | 15-35 | °C   | Range      |

## Safety Requirements

- Emergency stop response time: <100ms
- Robot must return to home position after 30 seconds of inactivity
- Maximum payload: 500g
- Collision detection must be enabled at all times

## Maintenance Schedule

- Daily: Visual inspection of gripper pads
- Weekly: Calibration check of position sensors
- Monthly: Full system diagnostic and firmware update
