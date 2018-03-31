#!/usr/bin/env python3
'''Author: jonathan lung (https://github.com/lungj)
Maybe I just stopped you from doing something foolish. Or in retrospect brilliant (d'oh).
In any case...
ETH/ETC: 0xc5500095A395B4FB3ba81bB0D8e316c675d1F47C

Data sourced from https://etherscan.io

THIS PROGRAM DOES NOT CONSTITUTE INVESTMENT ADVICE. IT IS OFFERED AS-IS AND WITHOUT
WARRANTY. See LICENSE file.

Basic simulation of Ethereum that models mining rewards with block propagation delays.

Things this does NOT simulate include:
 * mining speed changes due to epoch changes,
 * chain difficulty,
 * transactions,
 * transaction processing times,
 * chain weight due to GHOST, and
 * block propagation through peers (though this can be manually entered).
 
Due to the way the difficulty is set in this simulation, average block times in the
simulation will be slower than they ought to be. E.g., if a 15s block time is set,
the _actual_ expected average blocktime will be greater than 15s if block propagation time
is > 0 for mining nodes.
'''

import random
from time import sleep
from pprint import pformat

class Event(object):
    '''An event that goes into an EventQueue.'''
    def __init__(self, time, callback):
        self.time = time
        self.callback = callback
    
    def __call__(self):
        return self.callback()

class EventQueue(object):
    '''An event queue for calling functions at a later time.'''
    def __init__(self):
        self.pending = []
        
    def schedule(self, event):
        self.pending.append(event)
        self.pending.sort(key=lambda x: x.time)
    
    def process(self):
        for event in self.pending[:]:
            if time >= event.time:
                event()
                self.pending.pop(0)
            else:
                return

class Block(object):
    def __init__(self, height, miner=None, uncles=None, previous=None):
        '''Initialize a new block at height that follow block previous mined by miner with
        uncles.'''
        self.height = height
        self.previous = previous
        self.miner = miner
        self.uncles = uncles or set()
        if previous:
            self.balances = dict(previous.balances)
        else:
            self.balances = {}
        
        if miner:
            self.balances[miner] = self.balances.get(miner, 0) + BLOCKREWARD
        
        if uncles and miner:
            for uncle in uncles:
                # Reward for including uncle.
                self.balances[miner] = self.balances.get(miner, 0) + BLOCKREWARD / 32
                # Reward to miner of uncle.
                self.balances[uncle.miner] = self.balances.get(uncle.miner, 0) + \
                    ((self.height - uncle.height + 8) * BLOCKREWARD / 8)
    
    def can_be_uncle_of(self, other):
        '''Return True iff self can be an uncle block included in other.'''
        if self.height > other.height or self.height + 6 < other.height:
            return False
        
        cur_block = other
        while cur_block.height != self.height:
            if self == cur_block:                   # Can't be uncle in own main tree.
                return False
            if self in cur_block.uncles:
                return False                        # Can't include same uncle twice?
            cur_block = cur_block.previous
        
        return cur_block.previous == other.previous
    
    def __repr__(self):
        return str(id(self))
            

class Blockchain(object):
    genesis_block = Block(0)
    
    def __init__(self):
        '''Initialize a blockchain state from an arbitrary point in time where everyone is
        in sync.'''
        self.last_block = Blockchain.genesis_block
        self.potential_uncles = []
    
    def update(self, new_block):
        '''Update state based on newly received block new_block.'''

        # If the new block is farther along the chain than the currently known about
        # block, update chain state.
        if self.last_block.height < new_block.height:
            self.last_block = new_block
        
        else:
            if new_block.can_be_uncle_of(self.last_block):
                self.potential_uncles.append(new_block)

    def prune_uncle_candidates(self):
        '''Get rid of blocks in the potential uncle pool that can't be uncles.'''
        self.potential_uncles = [candidate for candidate in self.potential_uncles if \
            candidate.can_be_uncle_of(self.last_block)]

    def append(self, miner):
        '''Append a block to the chain mined by miner.'''

        self.prune_uncle_candidates()    
            
        use_uncles, self.potential_uncles = self.potential_uncles[:2], self.potential_uncles[2:]
        self.last_block = Block(self.last_block.height + 1, miner, use_uncles, self.last_block)
        
    def chain_history(self):
        retstr = ''
        cur_block = self.last_block
        while cur_block != Blockchain.genesis_block:
            retstr = str(cur_block) + ' ' + retstr
            cur_block = cur_block.previous
        
        return retstr

    def __repr__(self):
        return pformat(self.last_block.balances)

class Miner(object):
    def __init__(self, name, hashrate):
        '''Initialize a new miner named name with hashrate measured in hashes per second.'''
        self.name = name
        self.hashrate = hashrate
        self.chainstate = Blockchain()
        
    def latency_to(self, miner):
        '''Return the latency, in seconds, between self and miner.'''
        if self == miner:
            return 0

        if (self, miner) in LATENCIES:
            return LATENCIES[self, miner]()

        if (miner, self) in LATENCIES:
            return LATENCIES[miner, self]()

        return 0.2  # Just a static 200ms latency by default.

    def simulate_mining(self):
        if (random.random() * (TOTAL_HASHPOWER / self.hashrate)) < (TIMESTEP / BLOCKTIME):
            self.chainstate.append(self)
            
            for miner in MINERS:
                if miner != self:
                    evt = Event(time + self.latency_to(miner), (
                        lambda miner, block: lambda: miner.chainstate.update(block) 
                        )(miner, self.chainstate.last_block))
                    events.schedule(evt)
            return True
        return False

    def __repr__(self):
        return self.name

# List of miners in competition for blocks.
MINERS = [
    Miner('Alice', 30e6),
    Miner('Bob', 20e6),
    Miner('Charlie', 5e6),
    Miner('Duckworth Slowworthy', 30e6),        # If this is increased to be ~50% of
                                                # network speed or more, this provides
                                                # a weak facsimile of selfish mining.
]

# Time to broadcast blocks between miners.
# Assumes symmetry.
LATENCIES = {
    # Fixed delay of 0.1s between Alice and Bob.
    (MINERS[0], MINERS[1]): lambda: 0.1,
    
    # Average delay of 0.2s with standard deviation of 0.1s between Alice and Charlie.
    (MINERS[0], MINERS[2]): lambda: random.gauss(0.2, 0.1),
    
    # Unfortunate miner with very slow Internet -- 105s latency (7 blocks, by default).
    (MINERS[0], MINERS[3]): lambda: random.gauss(105, 15),
    (MINERS[1], MINERS[3]): lambda: random.gauss(105, 15),
    (MINERS[2], MINERS[3]): lambda: random.gauss(105, 15),
}

TIMESTEP = 0.01         # 0.01 seconds per timestep
BLOCKTIME = 15          # Average number of seconds per block
BLOCKREWARD = 3         # Reward for mining a block.


TOTAL_HASHPOWER = sum([miner.hashrate for miner in MINERS])
events = EventQueue()   # Initialize an event queue.
timesteps = 0

while True:
    time = timesteps * TIMESTEP
    for miner in MINERS:
        if miner.simulate_mining():
            print("t=%0.3fs: %s mined a block" % (time, miner.name))

    events.process()
    
    # Print out blockchain states every minute of simulated time.
    if timesteps % int(60 / TIMESTEP) == 0:
        for miner in MINERS:
            print(str(miner).ljust(20), '\t', miner.chainstate)
    
        sleep(1)
    timesteps += 1