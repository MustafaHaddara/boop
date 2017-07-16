#!/usr/bin/python

# Game Design summary:
## moving advances time (turn based)
##   also charges energy
## energy is used to send out pulse (explosion?)
##   also lets the player see around them
##   also tied to win condition (win when having a certain amount of energy)
## enemies endanger the player
##   killing enemy (by stabbing) lets you take an extra step (mobility/escape)
##     some enemies can be killed by walking into them (behind/sides)
##   others can't be killed at all except by pulse 
##      act as mobile walls, trapping the player, pressuring player to explode
##   killing enemy by pulse adds energy

import os
import random
import sys
import threading
import time

from datetime import datetime
from Queue import Queue

import pygame
from pygame.locals import *

RM_WIDTH = 672
RM_HEIGHT = 480
CELL_SIZE = 32

BLANK_CELL_COLOR = (192, 192, 192)
WALL_CELL_COLOR = (123, 94, 55)
LINE_COLOR = (160, 160, 160)
GOAL_COLOR = (0, 218, 67)
ENEMY_COLOR = (255, 0, 0)

class GameObject(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def pos(self):
        return (self.x, self.y)


class Cell(GameObject):
    def __init__(self, x, y, wall=False):
        super(self.__class__, self).__init__(x, y)
        self.wall = wall

    def draw(self, window):
        rect = pygame.Rect(self.x, self.y, CELL_SIZE, CELL_SIZE)
        color, lineColor = BLANK_CELL_COLOR, LINE_COLOR
        if self.isWall():
            color = WALL_CELL_COLOR

        window.fill(color, rect)
        if not self.isWall():
            pygame.draw.rect(window, lineColor, rect, 1)

    def flip(self):
        self.wall = not self.wall

    def __repr__(self):
        return "%s at (%s, %s)" % ("wall" if self.wall else "cell", self.x, self.y)

    def isWall(self):
        return self.wall


class Enemy(GameObject):
    def draw(self, window):
        center = (self.x + (CELL_SIZE / 2), self.y + (CELL_SIZE / 2))
        radius = CELL_SIZE / 8
        pygame.draw.circle(window, ENEMY_COLOR, center, radius)

    def getGridPos(self):
        return (self.x / CELL_SIZE, self.y / CELL_SIZE)


class Player(GameObject):
    def __init__(self, pos):
        super(self.__class__, self).__init__(pos.x, pos.y)
        self.pulse = None
        self.energy = 0

    def draw(self, window):
        center = (self.x + (CELL_SIZE / 2), self.y + (CELL_SIZE / 2))
        radius = CELL_SIZE / 4
        pygame.draw.circle(window, GOAL_COLOR, center, radius)
        if self.pulse is not None:
            self.pulse.draw(window)

    def move(self, direction, distance):
        self.energy += 1
        d = distance if not (direction == 'left' or direction == 'up') else -1*distance
        if direction == 'left' or direction == 'right':
            self.x += d
        elif direction == 'up' or direction == 'down':
            self.y += d

    def fire(self):
        pos = self.getCenter()
        self.pulse = Pulse(pos[0], pos[1], self.energy*10, self.clearPulse)
        self.energy = 0

    def getCenter(self):
        return (self.x + (CELL_SIZE / 2), self.y + (CELL_SIZE / 2))

    def clearPulse(self):
        self.pulse = None

    def getPulse(self):
        return self.pulse


class Pulse(GameObject):
    def __init__(self, x, y, energy, callback):
        super(self.__class__, self).__init__(x, y)
        self.energy = energy
        self.radius = 2
        self.killme = callback

    def draw(self, window):
        if (self.radius < self.energy):
            pygame.draw.circle(window, pygame.Color(255,255,255), self.pos(), self.radius, 1)
            self.radius += 1
        else:
            self.killme()

    def overlaps(self, x, y):
        x2 = (self.x - x)**2
        y2 = (self.y - y)**2
        dist = (x2 + y2)**0.5
        return (dist <= self.radius+2)


class GameController(object):
    def __init__(self):
        pygame.init()
        pygame.event.set_allowed([pygame.QUIT, MOUSEBUTTONDOWN])
        self.window = pygame.display.set_mode((RM_WIDTH, RM_HEIGHT))
        self.cells = []
        for y in range(0, RM_HEIGHT, CELL_SIZE):
            row = []
            for x in range(0, RM_WIDTH, CELL_SIZE):
                row.append(Cell(x, y))
            self.cells.append(row)

        self.player = Player(self.getCellXY(x=RM_WIDTH/(2*CELL_SIZE), y=RM_HEIGHT/(2*CELL_SIZE)))
        pos = self.normalizePixelCoord(self.player.pos())

        self.aiController = AIController()
        self.aiController.findPaths(self.cells, self.getCell(pos))

    def run(self):
        frameRate = 60
        clock = pygame.time.Clock()
        while True:
            start = datetime.now().microsecond

            playerInput = self.handleEvents()
            self.drawCells()
            self.player.draw(self.window)
            if playerInput:
                # AI doesn't get to move if the player hasn't moved
                self.aiController.computePositions()
            self.aiController.detectPulseCollisions(self.player.getPulse())
            self.aiController.draw(self.window)

            clock.tick_busy_loop(frameRate)
            pygame.display.flip()

    def handleEvents(self):
        for event in pygame.event.get():
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    self.quit()
                else:
                    return self.handleKey(event.key)
            elif event.type == QUIT:
                self.quit()

    def drawCells(self):
        for row in self.cells:
            for cell in row:
                cell.draw(self.window)

    def handleKey(self, keyCode):
        if keyCode == K_SPACE:
            self.player.fire()
        elif keyCode == K_UP:
            self.player.move('up', CELL_SIZE)
        elif keyCode == K_DOWN:
            self.player.move('down', CELL_SIZE)
        elif keyCode == K_RIGHT:
            self.player.move('right', CELL_SIZE)
        elif keyCode == K_LEFT:
            self.player.move('left', CELL_SIZE)
        else:
            return False
        pos = self.normalizePixelCoord(self.player.pos())
        self.aiController.findPaths(self.cells, self.getCell(pos))
        return True

    def quit(self):
        pygame.quit()
        self.aiController.quit()
        sys.exit()

    def getCell(self, pos):
        return self.getCellXY(x=pos[0], y=pos[1])

    def getCellXY(self, x, y):
        return self.cells[y][x]

    def normalizePixelCoord(self, coord):
        return (coord[0] / CELL_SIZE, coord[1] / CELL_SIZE)


class AIController(object):
    def __init__(self):
        self.frontier = Queue()
        # self.frontier.put(goal)
        self.edges = {}
        # self.edges[goal] = None
        self.enemies = []
        self.goal = None
        self.spawnLocations = [(CELL_SIZE, CELL_SIZE), 
                               (RM_WIDTH - 2*CELL_SIZE, CELL_SIZE), 
                               (RM_WIDTH - 2*CELL_SIZE, RM_HEIGHT - 2*CELL_SIZE), 
                               (CELL_SIZE, RM_HEIGHT - 2*CELL_SIZE)]
        self.killed = False
        self.spawnThread = threading.Thread(target=self.spawnThreadControl)
        self.spawnThread.start()

    def findPaths(self, cells, targetCell):
        self.goal = targetCell
        self.edges = {}
        self.edges[self.goal] = None
        self.cells = cells
        self.frontier.put(self.goal)
        while not self.frontier.empty():
            current = self.frontier.get()
            n = self.getNeighbors(current, cells)
            for toCheck in n:
                if toCheck not in self.edges:
                    self.frontier.put(toCheck)
                    self.edges[toCheck] = current

    def computePositions(self):
        toDelete = []
        for e in self.enemies:
            gridPos = e.getGridPos()
            loc = self.cells[gridPos[1]][gridPos[0]]
            if loc in self.edges:
                newLoc = self.edges[loc]
                if newLoc is None:
                    toDelete.append(e)
                else:
                    e.x = newLoc.x
                    e.y = newLoc.y
        for e in toDelete:
            self.enemies.remove(e)

    def detectPulseCollisions(self, pulse):
        if pulse is None:
            return
        toDelete = []
        for e in self.enemies:
            if pulse.overlaps(e.x + CELL_SIZE/2, e.y + CELL_SIZE/2):
                toDelete.append(e)
        for e in toDelete:
            self.enemies.remove(e)

    def draw(self, window):
        for e in self.enemies:
            e.draw(window)

    def spawnThreadControl(self):
        while not self.killed:
            time.sleep(2)
            self.spawnEnemy()

    def spawnEnemy(self):
        idx = random.randint(0, len(self.spawnLocations)-1)
        spawnLocation = self.spawnLocations[idx]
        e = Enemy(spawnLocation[0], spawnLocation[1])
        self.enemies.append(e)

    def quit(self):
        self.killed = True
        self.spawnThread.join()

    def nextCell(self, cell):
        return self.edges[cell]  # might be None

    def getNeighbors(self, cell, cells):
        x1 = (cell.x/CELL_SIZE) - 1
        x2 = (cell.x/CELL_SIZE) + 1
        y1 = (cell.y/CELL_SIZE) - 1
        y2 = (cell.y/CELL_SIZE) + 1

        yVals = self.checkVals(y1, y2, RM_HEIGHT / CELL_SIZE)
        xVals = self.checkVals(x1, x2, RM_WIDTH / CELL_SIZE)

        neighbors = []
        pos = []
        for y in yVals:
            pos.append([cell.x/CELL_SIZE, y])
        for x in xVals:
            pos.append([x, cell.y/CELL_SIZE])
        for p in pos:
            x,y = p
            c = cells[y][x]
            if not c.isWall():
                neighbors.append(c)

        return neighbors

    def checkVals(self, v1, v2, m=0):
        if v1 < 0:
            vals = [v2]
        elif v2 >= m:
            vals = [v1]
        else:
            vals = [v1, v2]
        return vals



def main():
    c = GameController()
    c.run()


if __name__ == '__main__':
    main()