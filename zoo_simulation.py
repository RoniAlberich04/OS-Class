import threading
import time
import random
import queue
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

class VisitorType(Enum):
    GOLD = 1
    SILVER = 2
    SCHOOL = 3
    REGULAR = 4

class VisitOption(Enum):
    OPEN_AREA = 1
    THEATER = 2
    BOTH = 3

@dataclass
class Visitor:
    id: int
    visitor_type: VisitorType
    visit_option: VisitOption
    entry_time: float
    in_open_area: bool = False
    in_theater: bool = False
    
    def get_priority(self) -> int:
        """Higher number = higher priority"""
        priorities = {
            VisitorType.GOLD: 4,
            VisitorType.SILVER: 3,
            VisitorType.SCHOOL: 2,
            VisitorType.REGULAR: 1
        }
        return priorities[self.visitor_type]

class Zoo:
    def __init__(self):
        self.open_area_capacity = 300
        self.theater_capacity = 30
        self.open_area_current = 0
        self.theater_current = 0
        
        # Locks for capacity management
        self.open_area_lock = threading.Lock()
        self.theater_lock = threading.Lock()
        
        # Visitors currently in the zoo
        self.active_visitors: List[Visitor] = []
        self.active_visitors_lock = threading.Lock()
        
        # Statistics
        self.total_visitors_served = 0
        self.stats_lock = threading.Lock()
        
    def can_enter_open_area(self, visitor: Visitor) -> bool:
        """Check if visitor can enter open area"""
        with self.open_area_lock:
            if visitor.visit_option in [VisitOption.OPEN_AREA, VisitOption.BOTH]:
                if self.open_area_current < self.open_area_capacity:
                    self.open_area_current += 1
                    visitor.in_open_area = True
                    return True
        return False
    
    def can_enter_theater(self, visitor: Visitor) -> bool:
        """Check if visitor can enter theater"""
        with self.theater_lock:
            if visitor.visit_option in [VisitOption.THEATER, VisitOption.BOTH]:
                if self.theater_current < self.theater_capacity:
                    self.theater_current += 1
                    visitor.in_theater = True
                    return True
        return False
    
    def leave(self, visitor: Visitor):
        """Visitor leaves the zoo"""
        with self.active_visitors_lock:
            if visitor in self.active_visitors:
                self.active_visitors.remove(visitor)
                
        # Release capacities
        if visitor.in_open_area:
            with self.open_area_lock:
                self.open_area_current -= 1
                
        if visitor.in_theater:
            with self.theater_lock:
                self.theater_current -= 1
                
        with self.stats_lock:
            self.total_visitors_served += 1
            
        logger.info(f"Visitor {visitor.id} ({visitor.visitor_type.name}) left the zoo")

class Gate(threading.Thread):
    def __init__(self, gate_id: int, zoo: Zoo, visitor_queues: Dict[VisitorType, queue.Queue]):
        super().__init__()
        self.gate_id = gate_id
        self.zoo = zoo
        self.visitor_queues = visitor_queues
        self.running = True
        self.starvation_counter = 0
        
    def stop(self):
        self.running = False
        
    def get_next_visitor(self) -> Optional[Visitor]:
        """Get next visitor based on priority, with starvation prevention"""
        # Check queues in priority order
        for visitor_type in [VisitorType.GOLD, VisitorType.SILVER, 
                            VisitorType.SCHOOL, VisitorType.REGULAR]:
            try:
                # Try to get visitor with timeout to prevent starvation
                visitor = self.visitor_queues[visitor_type].get(timeout=0.1)
                return visitor
            except queue.Empty:
                continue
        return None
    
    def process_visitor(self, visitor: Visitor):
        """Process a single visitor trying to enter"""
        logger.info(f"Gate {self.gate_id}: Processing {visitor.visitor_type.name} "
                   f"Visitor {visitor.id} (Option: {visitor.visit_option.name})")
        
        entered = False
        
        # Try to enter based on visit option
        if visitor.visit_option == VisitOption.OPEN_AREA:
            if self.zoo.can_enter_open_area(visitor):
                entered = True
        elif visitor.visit_option == VisitOption.THEATER:
            if self.zoo.can_enter_theater(visitor):
                entered = True
        else:  # BOTH
            # Try both areas, starting with the less crowded one
            with self.zoo.open_area_lock, self.zoo.theater_lock:
                open_area_available = self.zoo.open_area_current < self.zoo.open_area_capacity
                theater_available = self.zoo.theater_current < self.zoo.theater_capacity
                
            if open_area_available and not theater_available:
                entered = self.zoo.can_enter_open_area(visitor)
            elif theater_available and not open_area_available:
                entered = self.zoo.can_enter_theater(visitor)
            elif open_area_available and theater_available:
                # Both available, randomly choose one
                if random.choice([True, False]):
                    entered = self.zoo.can_enter_open_area(visitor)
                else:
                    entered = self.zoo.can_enter_theater(visitor)
        
        if entered:
            with self.zoo.active_visitors_lock:
                self.zoo.active_visitors.append(visitor)
            logger.info(f"Gate {self.gate_id}: Visitor {visitor.id} entered the zoo")
            self.starvation_counter = 0
        else:
            # Re-queue the visitor if they couldn't enter
            logger.warning(f"Gate {self.gate_id}: Visitor {visitor.id} couldn't enter "
                          f"(Capacity full), re-queuing")
            self.visitor_queues[visitor.visitor_type].put(visitor)
            self.starvation_counter += 1
            
            # Demonstrate starvation: if a queue gets starved, log it
            if self.starvation_counter > 5:
                logger.warning(f"Gate {self.gate_id}: Potential starvation detected! "
                             f"{visitor.visitor_type.name} visitors being repeatedly blocked")
    
    def run(self):
        while self.running:
            visitor = self.get_next_visitor()
            if visitor:
                self.process_visitor(visitor)
            else:
                time.sleep(0.1)  # No visitors, wait a bit

class VisitorGenerator:
    def __init__(self, zoo: Zoo, gates: List[Gate], visitor_queues: Dict[VisitorType, queue.Queue]):
        self.zoo = zoo
        self.gates = gates
        self.visitor_queues = visitor_queues
        self.running = True
        self.visitor_counter = 0
        
    def generate_visitor(self):
        """Generate a random visitor"""
        self.visitor_counter += 1
        visitor_type = random.choice(list(VisitorType))
        visit_option = random.choice(list(VisitOption))
        
        visitor = Visitor(
            id=self.visitor_counter,
            visitor_type=visitor_type,
            visit_option=visit_option,
            entry_time=time.time()
        )
        
        # Assign to random gate's queue
        gate = random.choice(self.gates)
        self.visitor_queues[visitor_type].put(visitor)
        logger.info(f"Generated {visitor_type.name} Visitor {visitor.id} "
                   f"(Option: {visit_option.name}) -> Gate {gate.gate_id}")
        
    def visitor_leaver(self):
        """Randomly make visitors leave"""
        while self.running:
            time.sleep(random.uniform(2, 5))
            with self.zoo.active_visitors_lock:
                if self.zoo.active_visitors:
                    visitor = random.choice(self.zoo.active_visitors)
                    self.zoo.leave(visitor)
    
    def run(self):
        """Main generator loop"""
        # Start leaver thread
        leaver_thread = threading.Thread(target=self.visitor_leaver)
        leaver_thread.daemon = True
        leaver_thread.start()
        
        # Generate visitors
        while self.running:
            # Generate 1-3 visitors per second
            time.sleep(random.uniform(0.3, 1))
            num_visitors = random.randint(1, 3)
            for _ in range(num_visitors):
                self.generate_visitor()
    
    def stop(self):
        self.running = False

def simulate_deadlock(zoo: Zoo, duration: int = 30):
    """
    Simulate a potential deadlock scenario where gold members 
    occupy all slots and block others
    """
    logger.info("=" * 60)
    logger.info("Starting Zoo Simulation with Deadlock/Starvation Demonstration")
    logger.info("=" * 60)
    
    # Create queues for each visitor type
    visitor_queues = {
        VisitorType.GOLD: queue.Queue(),
        VisitorType.SILVER: queue.Queue(),
        VisitorType.SCHOOL: queue.Queue(),
        VisitorType.REGULAR: queue.Queue()
    }
    
    # Create gates
    gates = [Gate(i, zoo, visitor_queues) for i in range(3)]
    
    # Start gates
    for gate in gates:
        gate.start()
    
    # Start visitor generator
    generator = VisitorGenerator(zoo, gates, visitor_queues)
    generator_thread = threading.Thread(target=generator.run)
    generator_thread.start()
    
    # Run simulation for specified duration
    try:
        time.sleep(duration)
        
        # Print statistics
        logger.info("=" * 60)
        logger.info("SIMULATION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total visitors served: {zoo.total_visitors_served}")
        
        with zoo.open_area_lock, zoo.theater_lock:
            logger.info(f"Current open area occupancy: {zoo.open_area_current}/{zoo.open_area_capacity}")
            logger.info(f"Current theater occupancy: {zoo.theater_current}/{zoo.theater_capacity}")
        
        logger.info("\nQueue sizes (showing potential starvation):")
        for visitor_type, q in visitor_queues.items():
            logger.info(f"  {visitor_type.name}: {q.qsize()} visitors waiting")
            
        # Demonstrate starvation by showing which queues are backing up
        if visitor_queues[VisitorType.REGULAR].qsize() > 10:
            logger.warning("⚠️ STARVATION DETECTED: Regular visitors are being starved!")
        if visitor_queues[VisitorType.SCHOOL].qsize() > 10:
            logger.warning("⚠️ STARVATION DETECTED: School groups are being starved!")
            
    except KeyboardInterrupt:
        logger.info("\nSimulation interrupted by user")
    finally:
        # Cleanup
        generator.stop()
        for gate in gates:
            gate.stop()
        
        generator_thread.join(timeout=2)
        for gate in gates:
            gate.join(timeout=2)
            
        logger.info("Simulation ended")

def main():
    """Main function to run the zoo simulation"""
    # Create zoo instance
    zoo = Zoo()
    
    # Run simulation for 60 seconds
    simulate_deadlock(zoo, duration=60)
    
    # Additional demonstration of deadlock scenario
    logger.info("\n" + "=" * 60)
    logger.info("DEADLOCK SCENARIO DEMONSTRATION")
    logger.info("=" * 60)
    logger.info("In this simulation, we demonstrated:")
    logger.info("1. Priority-based scheduling (Gold > Silver > School > Regular)")
    logger.info("2. Resource contention (Open area and Theater capacities)")
    logger.info("3. Starvation - Lower priority visitors get blocked by higher priority ones")
    logger.info("4. Potential deadlock - When both areas are filled with high-priority")
    logger.info("   visitors, lower priority visitors cannot enter at all")
    
    # Show how deadlock could happen
    logger.info("\nDeadlock scenario example:")
    logger.info("- 300 Gold members occupy the open area")
    logger.info("- 30 Gold members occupy the theater")
    logger.info("- All Gold members want both areas")
    logger.info("- Silver, School, and Regular visitors are completely blocked")
    logger.info("- This creates a deadlock where lower priority visitors")
    logger.info("  cannot enter the zoo at all")

if __name__ == "__main__":
    main()