from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Direction(Enum):
    up = "up"
    down = "down"

@dataclass
class Position:
    cause: str
    direction: str
    source: str
    status: str
    value: int

@dataclass
class Status:
    target_id: str
    position: Optional[Position] = None
    error: Optional[str] = None

    def is_moving(self) -> bool:
        return self.position.cause != 'target reached'

    def get_direction(self) -> Direction:
        if self.position.direction == 'up / open':
            return Direction.up

        return Direction.down

    @staticmethod
    def from_data(data: dict):
        result = data.get('result')
        if result is False:
            return Status(target_id=data['targetID'], error=data.get('error', {}).get('title'))

        position_data = data.get("position")
        position = Position(
            cause=position_data['cause'],
            direction=position_data['direction'],
            source=position_data['source'],
            status=position_data['status'],
            value=int(position_data['value'])
        )

        return Status(
            target_id=data['targetID'],
            position=position,
        )

@dataclass
class Device:
    ip: str
    mac: str

    @staticmethod
    def from_data(data: dict):
        return Device(data['ip'], data['mac'])