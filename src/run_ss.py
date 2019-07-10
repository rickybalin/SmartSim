
from state import State
from data_generation.generator import Generator
from control.controller import Controller

STATE = State()

# Data Generation Phase
GEN = Generator(STATE)
GEN.generate()

SIM = Controller(STATE)
SIM.start_sim()

