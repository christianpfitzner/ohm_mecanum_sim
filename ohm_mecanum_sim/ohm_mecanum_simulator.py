#!/usr/bin/env python3

# ------------------------------------------------------------
# Author:      Stefan May
# Date:        01.05.2024
# Description: Pygame-based robot simulator with ROS2 interface
# ------------------------------------------------------------

import pygame
import pygame.freetype  # Import the freetype module.
import sys

import rclpy
from rclpy.node import Node
from rclpy.clock import Clock

from ohm_mecanum_sim.robot import Robot

class Ohm_Mecanum_Simulator(Node):

    def __init__(self, surface, rosname, windowtitle):
        super().__init__(rosname)
        self._surface = surface
        self._background = pygame.Surface(self._surface.get_size())
        self._meter_to_pixel = 100
        self._robots = []
        self._line_segment_obstacles = []
        self._verbose = False

        self._laptime_start = 0


        _default_callback_group = Node.default_callback_group
        timer_period = 0.05
        pygame.display.set_caption(windowtitle)

    def __del__(self):
        pass

    def start_scheduler(self):
        clock = pygame.time.Clock()
        clock.tick(360)
        timer_period = 0.02
        self.timer = self.create_timer(timer_period, self.timer_callback)


    def ui_scheduler(self):
        clock = pygame.time.Clock()
        clock.tick(360)
        timer_period = 0.1
        self.ui_timer = self.create_timer(timer_period, self.ui_timer_callback)


    def ui_timer_callback(self):
        print("UI Timer Callback")
        


    def start_laptime(self):
        self._laptime_start  = pygame.time.get_ticks() 


    def stop_laptime(self):
        laptime = pygame.time.get_ticks() - self._laptime_start
        print("Laptime: " + str(laptime) + " ms")


    def reset_laptime(self):
        self.stop_laptime()
        self._laptime_start = 0


    def get_running_laptime(self):

        laptime = pygame.time.get_ticks() - self._laptime_start

        print ("Laptime: " + str(laptime) + " ms")
        # return pygame.time.get_ticks() - self._laptime_start


    def timer_callback(self):
        bg_color = (64, 64, 255)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit_simulation()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_c and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.exit_simulation()
        self._surface.fill(bg_color)

        self._background.fill((0, 255, 0))
        pygame.draw.rect(self._background, (0, 0, 255), (400, 600, 10, 300))


        self._background.set_alpha(128)
        # self._background.blit(self._surface, (0, 0))
        self._surface.blit(self._background, (0, 0))


        # Draw obstacles
        for obstacle in self._line_segment_obstacles:
            pixel_segment_start = self.transform_to_pixelcoords(obstacle[0])
            pixel_segment_end = self.transform_to_pixelcoords(obstacle[1])
            pygame.draw.line(self._surface, pygame.Color(0, 0, 0), pixel_segment_start, pixel_segment_end, 3)

        # Convert robot coordinates for displaying all entities in pixel coordinates
        for r in self._robots:

            r.acquire_lock()
            # Draw robot symbol
            coords      = r.get_coords()
            pixel_robot = self.transform_to_pixelcoords(coords)
            rect        = r.get_rect()
            rect.center = pixel_robot
            rect.move(pixel_robot)
            self._surface.blit(r.get_image(), rect)

            pos_sensor = r.get_pos_tof()
            pos_hitpoint = r.get_far_tof()

            # Determine distances to other robots
            dist_to_obstacles  = []
            for obstacle in self._robots:
                if(obstacle != r):
                    obstacle_coords = obstacle.get_coords()
                    dist_to_obstacles = r.get_distance_to_circular_obstacle(obstacle_coords, obstacle.get_obstacle_radius(),  dist_to_obstacles)

                    # Draw circular radius of obstacle
                    if(self._verbose):
                        pixel_obstacle = self.transform_to_pixelcoords(obstacle_coords)
                        obstacle_rect = obstacle.get_rect()
                        obstacle_rect.center = pixel_obstacle
                        obstacle_rect.move(pixel_obstacle)
                        pygame.draw.circle(self._surface, (255, 0, 0), (int(pixel_obstacle[0]), int(pixel_obstacle[1])), int(obstacle.get_obstacle_radius()*self._meter_to_pixel), 1)

            # Determine distances to line segments
            for obstacle in self._line_segment_obstacles:
                dist_to_obstacles = r.get_distance_to_line_obstacle(obstacle[0], obstacle[1], dist_to_obstacles)

            r.publish_tof(dist_to_obstacles)

            r.release_lock()

            min_dist = 9999
            for i in range(0, len(dist_to_obstacles)):
                if(dist_to_obstacles[i]<min_dist and dist_to_obstacles[i]>0):
                    min_dist = dist_to_obstacles[i];
            if(min_dist<(0.2+r._offset_tof)):
                r.reset_pose()
            elif (r._coords[0] < 0 or r._coords[1] < 0 or r._coords[0] > self._surface.get_width()/self._meter_to_pixel or r._coords[1] > self._surface.get_height()/self._meter_to_pixel):
                r.reset_pose()




            # todo make this more flexible
            # start the lap timer
            if r._coords[0] < 4.2  and r._coords[0] > 4.10 and r._coords[1] < 3.00 and r._coords[1] > 0.0:
                self.start_laptime()


            # check if the robot is on the finish line
            if r._coords[0] < 4.1  and r._coords[0] > 4.00 and r._coords[1] < 3.00 and r._coords[1] > 0.0:
                self.stop_laptime()

            # Draw ToF beams
            pos_hitpoint = r.get_hit_tof(dist_to_obstacles)
            for i in range(0,r.get_tof_count()):
                pixel_sensor = self.transform_to_pixelcoords(pos_sensor[i])
                pixel_hitpoint = self.transform_to_pixelcoords(pos_hitpoint[i])
                pygame.draw.line(self._surface, pygame.Color(255, 0, 0, 128), pixel_sensor, pixel_hitpoint)  

        pygame.display.update()
    
    def spawn_robot(self, x, y, theta, name):
        robot = Robot(x, y, theta, name, self._default_callback_group)
        self._robots.append(robot)
        return robot

    def kill_robot(self, name):
        for r in self._robots:
            if(r._name == name):
                r.stop()
                self._robots.remove(r)

    def add_line_segment_pixelcoords(self, coords1, coords2):
        line_segment = (self.transform_to_robotcoords(coords1), self.transform_to_robotcoords(coords2))
        self.add_line_segment_obstacle(line_segment)

    def add_rectangle_pixelcoords(self, coords1, coords2):
        line_segment = (self.transform_to_robotcoords([coords1[0], coords1[1]]), self.transform_to_robotcoords([coords1[0], coords2[1]]))
        self.add_line_segment_obstacle(line_segment)
        line_segment = (self.transform_to_robotcoords([coords1[0], coords2[1]]), self.transform_to_robotcoords([coords2[0], coords2[1]]))
        self.add_line_segment_obstacle(line_segment)
        line_segment = (self.transform_to_robotcoords([coords2[0], coords2[1]]), self.transform_to_robotcoords([coords2[0], coords1[1]]))
        self.add_line_segment_obstacle(line_segment)
        line_segment = (self.transform_to_robotcoords([coords2[0], coords1[1]]), self.transform_to_robotcoords([coords1[0], coords1[1]]))
        self.add_line_segment_obstacle(line_segment)


    def add_finish_line(self, coords1, coords2):
        pass

        # insert line in the background 
        # self._surface.add_line_segment_pixelcoords(coords1, coords2)




    def add_line_segment_obstacle(self, line_segment):
        self._line_segment_obstacles.append(line_segment)

    def transform_to_pixelcoords(self, coords):
        pixelcoords  = [ coords[0] * self._meter_to_pixel,
                        (self._surface.get_height() - coords[1] * self._meter_to_pixel) ]
        return pixelcoords

    def transform_to_robotcoords(self, coords):
        pixelcoords  = [ coords[0] / self._meter_to_pixel,
                         (-coords[1] + self._surface.get_height()) / self._meter_to_pixel]
        return pixelcoords

    def exit_simulation(self):
        print("Exit simulation")
        for r in self._robots:
            r.stop()
            del r
        sys.exit()
