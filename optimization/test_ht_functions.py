import math
import pytest
from random import uniform
import physical_properties as pp
from ht_functions import Flow, oned_flow_modeling

# parameters for test cases
N = 6
core_r = 0.16
radius = 0.005
fuel_frac = 1 - (N*radius*radius*math.pi) / (core_r*core_r*math.pi)
c = 0.00031
L = core_r
AR = 1
power = 1e5
T = (900, 1000)
P = (17.9e6, 17.4e6)
m_dot = 1
coolant = 'CO2'
fuel = 'UW'

# get secondary flow properties
flow_props = pp.FlowProperties(coolant, power, m_dot, T, P)

def test_set_geom():
    """Test geometry initialization. This tests the Flow method that calculates
    flow area, fuel area and hydraulic diameter.
    """
    test = Flow(radius, c, AR, power, fuel, coolant, flow_props)
    test.core_r = core_r
    test.fuel_frac = fuel_frac
    # expected values
    exp_De = radius * 2.0
    exp_A_flow = (1-fuel_frac) * core_r**2 * math.pi
    exp_A_fuel = core_r**2 * math.pi * fuel_frac
    # calculated values
    test.set_geom()
    # compare
    assert exp_De == test.D_e
    assert abs(exp_A_flow - test.A_flow) < 1e-7
    assert exp_A_fuel == test.A_fuel

def test_characterize_flow():
    """Test flow characterization. This tests the Flow method that calculates
    important thermophysical flow characteristics like velocity, friction
    factor, and average heat-transfer coefficient.
    """
    test = Flow(radius, c, AR, power, fuel, coolant, flow_props)
    test.core_r = core_r
    test.fuel_frac = fuel_frac
    # get geom
    test.set_geom()
    # expected flow velocity
    exp_G = test.fps.m_dot / (test.A_flow)
    exp_v = exp_G / test.fps.rho
    # expected heat transfer coefficient
    exp_Re = test.fps.rho * exp_v * test.D_e / test.fps.mu

    LD = L / (2*radius) 
    relrough = test.cladprops['rough'] / (2*radius)
    
    # correlation take from EES
    exp_f = 0.003030597
    exp_Nu = 126.0544263 
    exp_h = 1096.8527578
    
    print(test.D_e)
    # calculated values
    test.characterize_flow()
    # compare
    assert abs(exp_v - test.v) < 1e-7
    assert abs(exp_f - test.f) < 1e-7
    assert abs(exp_Nu - test.Nu) < 1e-7
    assert abs(exp_h - test.h_bar) < 1e-5

def test_q():
    """Test q_per_channel calculation. This tests the Flow method that
    calculates the thermal power generated by each fuel channel.
    """
    test = Flow(radius, c, AR, power, fuel, coolant, flow_props)
    test.fuel_frac = fuel_frac
    test.core_r = core_r
    # get geom and flow conditions
    test.set_geom()
    
    # force N channels for testing purposes
    test.N_channels = N
    test.characterize_flow()
    
    # expected value
    exp_q_gen = 8432.851535
    test.get_q_per_channel()
    
    # compare
    assert abs(exp_q_gen - test.gen_Q) < 1.0


def test_dp():
    """Test subchannel dp calculation. This tests the function that calculates
    the pressure drop in each flow channel.
    """
    test = Flow(radius, c, AR, power, fuel, coolant, flow_props)
    test.core_r = core_r
    test.fuel_frac = fuel_frac
    test.set_geom()
    test.characterize_flow()
    test.calc_dp()
    # expected dp
    exp_dp = test.f * L * test.fps.rho * test.v ** 2 / (2*test.D_e)
    # compare
    assert (exp_dp - test.dp)**2 < 1e-5

def test_rand_flow_calc():
    """Try random (r, PD, L) calculation and check by using the answer for
    N_channels to re-calculate q_per_channel. Compare the two q_per_channels to
    verify the results.
    """
    # random check oned_flow_modeling
    rand_r = uniform(0.005, 0.01)
    rand_power = uniform(90000, 150000)
    
    # calculate q_per_channel using random geom
    obs = Flow(rand_r, c, AR, rand_power, fuel, coolant, flow_props)
    oned_flow_modeling(obs)
    # check result manually
    exp = Flow(rand_r, c, AR, rand_power, fuel, coolant, flow_props)
    exp.fuel_frac = obs.fuel_frac
    exp.core_r = obs.core_r
    # get geom and flow conditions
    exp.set_geom()
    exp.characterize_flow()
    # expected value
    exp.get_q_per_channel()
    
    assert abs(exp.gen_Q - obs.gen_Q) < 1.0
