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
from pygame import gfxdraw

RM_WIDTH = 672
RM_HEIGHT = 480
CELL_SIZE = 32

BLANK_CELL_COLOR = (96, 96, 96)
WALL_CELL_COLOR = (48, 48, 48)
LINE_COLOR = (160, 160, 160)
GOAL_COLOR = (0, 218, 67)
ENEMY_COLOR = (255, 0, 0)
UI_COLOR_FILLED = (255,255,255)
UI_COLOR_UNFILLED = (128,128,128)

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
        color = BLANK_CELL_COLOR
        if self.isWall():
            color = WALL_CELL_COLOR

        window.fill(color, rect)
        # if not self.isWall():
        #     pygame.draw.rect(window, LINE_COLOR, rect, 1)

    def flip(self):
        self.wall = not self.wall

    def __repr__(self):
        return "%s at (%s, %s)" % ("wall" if self.wall else "cell", self.x, self.y)

    def isWall(self):
        return self.wall


class Enemy(GameObject):
    def __init__(self, x, y):
        super(Enemy, self).__init__(x, y)
        self.color = ENEMY_COLOR
        self.radius = CELL_SIZE / 8

    def draw(self, window):
        center = (self.x + (CELL_SIZE / 2), self.y + (CELL_SIZE / 2))
        gfxdraw.filled_circle(window, center[0], center[1], self.radius, self.color)

    def getGridPos(self):
        return (self.x / CELL_SIZE, self.y / CELL_SIZE)

    def move(self, pos):
        self.x = pos.x
        self.y = pos.y


class EnemyWall(Enemy):
    def __init__(self, x, y, createWall):
        super(self.__class__, self).__init__(x, y)
        self.color = UI_COLOR_FILLED
        self.radius = self.radius * 2
        self.lifetime = 20
        self.killme = createWall
        self.darkened = False

    def draw(self, window):
        super(self.__class__, self).draw(window)
        if self.lifetime == 0:
            self.killme(self)
        if self.lifetime in [10, 5, 3,2,1]:
            self.darken()
    
    def move(self, pos):
        super(self.__class__, self).move(pos)
        self.lifetime -= 1
        self.darkened = False

    def darken(self):
        if not self.darkened:
            self.color = tuple(max(i-16, 0) for i in self.color)
            self.darkened = True


class Player(GameObject):
    def __init__(self, pos):
        super(self.__class__, self).__init__(pos.x, pos.y)
        self.pulse = None
        self.killed = None
        self.energy = 0

    def draw(self, window):
        center = (self.x + (CELL_SIZE / 2), self.y + (CELL_SIZE / 2))
        radius = CELL_SIZE / 4
        gfxdraw.filled_circle(window, center[0], center[1], radius, GOAL_COLOR)
        if self.pulse is not None:
            self.pulse.draw(window)
        if self.killed is not None:
            self.killed.draw(window)

    def move(self, pos):
        self.energy += 1
        self.x,self.y = pos

    def fire(self):
        pos = self.getCenter()
        self.pulse = Pulse(pos[0], pos[1], self.getCharges(), self.clearPulse)
        self.energy = 0

    def getCenter(self):
        return (self.x + (CELL_SIZE / 2), self.y + (CELL_SIZE / 2))

    def clearPulse(self):
        self.pulse = None

    def getPulse(self):
        return self.pulse

    def getEnergyString(self):
        return 'Energy: ' + str(self.energy)

    def killedEnemy(self):
        self.energy += 1
        pos = self.getCenter()
        self.killed = Pulse(pos[0], pos[1], 0, self.clearKillAnim)
        self.killed.color = GOAL_COLOR

    def clearKillAnim(self):
        self.killed = None

    def getCharges(self):
        # 0     -> 0
        # 1-10  -> 1
        # 11-25 -> 2
        # 25-75 -> 3
        # 75+   -> 4
        if self.energy >= 75:
            return 4
        elif self.energy >= 25:
            return 3
        elif self.energy >= 10:
            return 2
        elif self.energy >= 1:
            return 1
        else:
            return 0

    def drawCharges(self, window):
        charges = self.getCharges()
        # 5 circles, rad = 20
        for i in xrange(4):
            xoffset = 12
            xdist = 10 + (i**2)/2
            y = 32
            x = xoffset+(i*xdist)
            # if i>0:
            color = UI_COLOR_FILLED if i<charges else UI_COLOR_UNFILLED
            self.drawRings(window, i, (x,y), color)

    def drawRings(self, window, numRings, center, color):
        radius = 2
        numRings = numRings*2
        gfxdraw.pixel(window, center[0], center[1], color)
        while numRings > 0:
            numRings -= 1
            radius += 1
            if numRings%2:
                gfxdraw.circle(window, center[0],center[1], radius, color)


class Pulse(GameObject):
    def __init__(self, x, y, energy, callback):
        super(self.__class__, self).__init__(x, y)
        self.energy = energy * CELL_SIZE + (CELL_SIZE/2)
        self.radius = 2
        self.killme = callback
        self.color = UI_COLOR_FILLED

    def draw(self, window):
        if (self.radius < self.energy):
            gfxdraw.circle(window, self.x, self.y, self.radius, self.color)
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
        self.font = pygame.font.Font(None, 20)

        self.cells = []
        maxX = RM_WIDTH  - CELL_SIZE
        maxY = RM_HEIGHT - CELL_SIZE
        for y in range(0, RM_HEIGHT, CELL_SIZE):
            row = []
            for x in range(0, RM_WIDTH, CELL_SIZE):
                c = Cell(x, y, (x==0 or x==maxX or y==0 or y==maxY))
                row.append(c)
            self.cells.append(row)

        self.player = Player(self.getCellXY(x=RM_WIDTH/(2*CELL_SIZE), y=RM_HEIGHT/(2*CELL_SIZE)))
        pos = self.normalizePixelCoord(self.player.pos())
        self.killSpot = None
        self.killAnim = 0

        self.aiController = AIController(self.evolveWall)
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
            self.drawUI()

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

    def drawUI(self):
        text = self.font.render(self.player.getEnergyString(), True, UI_COLOR_FILLED)
        self.window.blit(text, (6,6))
        self.player.drawCharges(self.window)

    def handleKey(self, keyCode):
        oldPlayerPos = self.player.pos()
        if keyCode == K_SPACE:
            self.player.fire()
            return False
        elif keyCode == K_UP:
            self.movePlayer('up', CELL_SIZE)
        elif keyCode == K_DOWN:
            self.movePlayer('down', CELL_SIZE)
        elif keyCode == K_RIGHT:
            self.movePlayer('right', CELL_SIZE)
        elif keyCode == K_LEFT:
            self.movePlayer('left', CELL_SIZE)
        else:
            return False
        return True

    def movePlayer(self, direction, distance):
        oldPlayerPos = self.player.pos()
        oldCoords = self.normalizePixelCoord(oldPlayerPos)

        # compute new position
        d = distance if not (direction == 'left' or direction == 'up') else -1*distance
        if direction == 'left' or direction == 'right':
            newPos = (oldPlayerPos[0]+d, oldPlayerPos[1])
        elif direction == 'up' or direction == 'down':
            newPos = (oldPlayerPos[0], oldPlayerPos[1]+d)

        # can we move into this spot?
        # first, get this location as a cell coordinate
        coords = self.normalizePixelCoord(newPos)
        cell = self.getCell(coords)
        # is there a wall here?
        if not cell.isWall():
            self.player.move(newPos)
            # is there an enemy on this spot? if so, kill it
            maybeEnemy = self.aiController.findEnemyInCell(coords)
            if maybeEnemy is not None and not isinstance(maybeEnemy, EnemyWall):
                self.aiController.killEnemy(maybeEnemy)
                self.player.killedEnemy()

        # recompute AI paths
        self.aiController.findPaths(self.cells, self.getCell(oldCoords))

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

    def evolveWall(self, enemy):
        self.aiController.killEnemy(enemy)
        coords = self.normalizePixelCoord(enemy.pos())
        self.getCell(coords).flip()


class AIController(object):
    def __init__(self, evolveWallCallback):
        self.frontier = Queue()
        self.edges = {}
        self.enemies = []
        self.goal = None
        self.spawnLocations = [(CELL_SIZE, CELL_SIZE), 
                               (RM_WIDTH - 2*CELL_SIZE, CELL_SIZE), 
                               (RM_WIDTH - 2*CELL_SIZE, RM_HEIGHT - 2*CELL_SIZE), 
                               (CELL_SIZE, RM_HEIGHT - 2*CELL_SIZE)]
        self.killed = False
        self.evolveWall = evolveWallCallback
        self.spawnThread = threading.Thread(target=self.spawnThreadControl)
        self.spawnThread.start()

    def findEnemyInCell(self, gp):
        for e in self.enemies:
            if e.getGridPos() == gp:
                return e
        return None

    def killEnemy(self, e):
        self.enemies.remove(e)

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
                    e.move(newLoc)
        for e in toDelete:
            self.killEnemy(e)

    def detectPulseCollisions(self, pulse):
        if pulse is None:
            return
        toDelete = []
        for e in self.enemies:
            if pulse.overlaps(e.x + CELL_SIZE/2, e.y + CELL_SIZE/2):
                toDelete.append(e)
        for e in toDelete:
            self.killEnemy(e)

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
        if random.randint(0,3):
            e = Enemy(spawnLocation[0], spawnLocation[1])
        else:
            e = EnemyWall(spawnLocation[0], spawnLocation[1], self.evolveWall)
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

        random.shuffle(neighbors)
        return neighbors

    def checkVals(self, v1, v2, m):
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
