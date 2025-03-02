import numpy as np
from typing import Tuple, List, Dict


class OccupancyGrid:
    def __init__(self, width: int=100, height: int=100, resolution: float=0.5):
        """
        initialize occupancy grid
        args:
            width: int: width of grid
            height: int: height of grid
            resolution: float: resolution of grid
        """
        
        self.width = width
        self.height = height
        self.resolution = resolution
        
        # initialize grid
        # 0-100 -> probability of cell being occupied
        # -1 -> cell is unknown
        self.grid = np.full((self.width, self.height), -1, dtype=np.int8)
        
        # map origin (center)
        self.origin = (width//2, height//2)
        
    def update_cell(self, x: int, y: int, occupied: bool, sensor_accuracy: float=0.9):
        """
        update cell in grid using probabilistic sensor model
        args:
            x, y: coordinates of cell
            occupied: true if the sensor detected an obstacle
            sensor_accuracy: precision of sensor
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        
        current = self.grid[y, x]
        if current == -1:
            # first observation
            self.grid[y, x] = 100 if occupied else 50
        else:
            # baysian update
            prior = current / 100.0
            if occupied:
                posterior = (sensor_accuracy * prior) / (sensor_accuracy * prior + (1 - sensor_accuracy) * (1 - prior))
            else:
                posterior = ((1 - sensor_accuracy) * prior) / ((1 - sensor_accuracy) * prior + sensor_accuracy * (1 - prior))
            
            self.grid[y, x] = int(posterior * 100)
            
    def world_to_grid(self, world_x: float, world_y: float) -> tuple[int, int]:
        """"convert coordinates from world to grid"""
        grid_x = int(world_x / self.resolution) + self.origin[0]
        grid_y = int(world_y / self.resolution) + self.origin[1]
        return grid_x, grid_y
    
    def update_from_scan(self, robot_pose: Tuple[float, float, float], scan_data: List[Dict[str, float]]):
        """
        update map using scan data
        args:
        robot_pose: (x, y, theta) in world coordinates
        scan_data: list of sensor readings (distance, angle)
        """
        
        robot_x, robot_y, robot_theta = robot_pose
        
        for scan in scan_data:
            angle = scan['inertial_angle']
            distance = scan['base_distance']
            
            # convert coordinates: polar to cartesian
            world_x = robot_x + distance * np.cos(robot_theta + angle)
            world_y = robot_y + distance * np.sin(robot_theta + angle)
            
            # update cells
            grid_x, grid_y = self.world_to_grid(world_x, world_y)
            self.update_cell(grid_x, grid_y, occupied=True)
            
            # mark the cells in the path as free
            robot_grid_x, robot_grid_y = self.world_to_grid(robot_x, robot_y)
            self._mark_free_cells(robot_grid_x, robot_grid_y, grid_x, grid_y)
            
    def _mark_free_cells(self, x0: int, y0: int, x1: int, y1: int):
        """
        mark cells in the path as free
        args:
            x0, y0: start coordinates
            x1, y1: end coordinates
        """
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        
        x = x0
        y = y0
        n = 1 + dx + dy
        x_inc = 1 if x1 > x0 else -1
        y_inc = 1 if y1 > y0 else -1
        error = dx - dy
        dx *= 2
        dy *= 2
        
        for _ in range(n):
            self.update_cell(x, y, occupied=False)
            if error > 0:
                x += x_inc
                error -= dy
            else:
                y += y_inc
                error += dx
                