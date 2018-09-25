# Other Imports
import math
from scipy.optimize import minimize_scalar
from physical_properties import phys_props

def pipeflow_turbulent(Re, Pr, LD, relrough):
    """Turbulent pipeflow correlation from EES. This function proiveds a nusselt
    number and friction factor for turbulent flow in a pipe.

    Arguments:
    ----------
        Re (float): flow Reynold's number [-]
        Pr (float): flow Prandtl number [-]
        LD (float): length over diameter [-]
        relrough (float) : relative roughness [-]
    
    Returns:
    --------
        Nusselt_L (float): nusselt number
        f (float): friction factor
    """

    #From Li, Seem, and Li, "IRJ, 
    #"A New Explicity Equation for Accurate Friction Factor 
    # Calculation for Smooth Tubes" 2011
    f_fd=(-0.001570232/math.log(Re) +
           0.394203137/math.log(Re)**2 +
           2.534153311/math.log(Re)**3) * 4 
    
    if relrough > 1e-5:
        #Offor and Alabi, 
        #Advances in Chemical Engineering and Science, 2016, 6, 237-245
        f_fd=(-2*math.log(
                 (relrough/3.71) -
                 (1.975/Re) * math.log((relrough/3.93)**1.092 +
                 (7.627/(Re + 395.9)) , 10))) ** (-2)
    
    #Gnielinski, V.,, Int. Chem. Eng., 16, 359, 1976
    Nusselt_L= ((f_fd/8)*(Re-1000)*Pr)/(1+12.7*math.sqrt(f_fd/8)*(Pr **(2/3) - 1)) 
    
    if (Pr<0.5):
        # Notter and Sleicher, Chem. Eng. Sci., Vol. 27, 1972
        Nusselt_L_lp =4.8 + 0.0156 * Re**0.85 * Pr**0.93
        if (Pr<0.1):
            Nusselt_L = Nusselt_L_lp
        else:
            Nusselt_L = Nusselt_L_lp+(Pr-0.1)*(Nusselt_L-Nusselt_L_lp)/0.4

    #account for developing flow
    f=f_fd*(1+(1/LD)**0.7) 
    Nusselt_L*=(1+(1/LD)**0.7)
    
    return Nusselt_L, f

def pipeflow_laminar(Re, Pr, LD, relrough):
    """Laminar pipeflow correlation from EES. This function provides a nusselt
    number and friction factor for laminar flow in a pipe.

    Arguments:
    ----------
        Re (float): flow Reynold's numbe [-]
        Pr (float): flow Prandtl number [-]
        LD (float): length over diameter [-]
        relrough (float) : relative roughness [-]
    
    Returns:
    --------
        Nusselt_T (float): nusselt number at constant temperature
        Nusselt_H (float): nusselt number at constant heat flux
        f (float): friction factor
    """

    Gz = Re* Pr /LD     
    x = LD / Re
    fR = 3.44 / math.sqrt(x) +\
        (1.25/(4*x) + 16 - 3.44/math.sqrt(x)) /\
        (1 + 0.00021 * x**(-2))

    f = 4 * fR / Re
    Gm = Gz**(1/3)
    Nusselt_T = 3.66 + ((0.049+0.02/Pr)*Gz**1.12)/(1+0.065*Gz**0.7)
    Nusselt_H = 4.36 + ((0.1156 +0.08569 /Pr**0.4)*Gz)/(1+0.1158*Gz**0.6) 
    
    return Nusselt_T, Nusselt_H, f
    
def pipeflow_nd(Re, Pr, LD, relrough):
    """Nusselt correlation procedure from EES. This function provides a nusselt
    number and friction factor for flow in a pipe. It accounts for laminar,
    turbulent and transistional flow.
    
    Arguments:
    ----------
        Re (float): flow Reynold's numbe [-]
        Pr (float): flow Prandtl number [-]
        LD (float): length over diameter [-]
        relrough (float) : relative roughness [-]
    
    Returns:
    --------
        Nusselt_T (float): nusselt number at constant temperature
        Nusselt_H (float): nusselt number at constant heat flux
        f (float): friction factor
    """
    if Re > 3000:
        Nusselt_T, f = pipeflow_turbulent(Re, Pr, LD, relrough)
        Nusselt_H = Nusselt_T
    elif Re < 2300:
        Nusselt_T, Nusselt_H, f = pipeflow_laminar(Re, Pr, LD, relrough)
    else:
        # transistion from laminar to turbulent
        
        # get turbulent
        Nusselt_T, f = pipeflow_turbulent(3000, Pr, LD, relrough)
        Nusselt_H = Nusselt_T
        
        # get laminar
        Nusselt_lam_T, Nusselt_lam_H, f_lam = pipeflow_laminar(2300, Pr, LD, relrough)
        
        # mix the two
        Nusselt_T=Nusselt_lam_T+(Re-2300)/(3000-2300)*(Nusselt_T-Nusselt_lam_T) 
        Nusselt_H=Nusselt_lam_H+(Re-2300)/(3000-2300)*(Nusselt_H-Nusselt_lam_H) 

        f=f_lam+(Re-2300)/(3000-2300)*(f-f_lam) 

    return Nusselt_T, Nusselt_H, f

def oned_flow_modeling(analyze_flow):
    """1D calculation.
    This function produces a valid, coolable reactor design given the following
    arguments:

    Arguments:
    ----------
        analyze_flow (flow) Flow object with methods and attributes to calculate
        N_channels.
    Returns:
    --------
        None
    """
    find_n_channels(analyze_flow)
    analyze_flow.adjust_dp()
    analyze_flow.calc_reactor_mass()


def _calc_n_channels_error(guess, flowiteration):
    """Calculate squared error between guess value and N channels for all
    three guess values.

    Arguments:
    ----------
        guess: a guess value for N_channels
        flowiteration: class containing TH methods and attributes

    Returns:
    --------
        error: difference between guess fuel channels and calculated required
        N_channels (float)
    """
    return flowiteration.compute_Q_from_guess(guess)


def find_n_channels(flow):
    """Perform error minimization. Using scipy's optimization package, call
    the _error function until the error is minimized to a set tolerance.

    Arguments:
    ----------
        flow: (class) Flow object. Contains attributes and
        methods required to perform an N_channels calculation for a single
        geometry (r, PD, L, c)
    Returns:
    --------
        none

    """
    res = minimize_scalar(_calc_n_channels_error, bounds=(0.01, 1), args=(flow),
                          method='Bounded', options={'xatol': 1e-3})


class Flow:
    """ Perform 1D Flow Analysis

    This class contains the required methods to perform a 1D coupled heat
    transfer/fluid flow problem on a CERMET Flow Channel.
    """
    savedata = {'mass': ("Total Fuel Mass", "m [kg]"),
                'N_channels': ("Number of Fuel Channels", "N Channels [-]"),
                'dp': ("Subchannel Pressure Drop", "dP [Pa]"),
                'h_bar': ("Heat Transfer Coefficient", "h [W / m^2 - K]"),
                'q_per_channel': ("Total Subchannel Generation", "q/channel [W]"),
                'q_bar': ("Average Volumetric Generation", "q_bar [W/m^3]"),
                'v': ("Flow Velocity", "v [m/s]"),
                'AR': ("Approximate Core Aspect Ratio", "AR [-]")
               }

    ################################
    # UNIT SYSTEM: m, kg, J, W, Pa #
    ################################

    # geometric attributes
    r_channel = 0
    c = 0  # clad thickness
    pitch = 0  # fuel pitch (center to side of hex)
    L = 0  # reactor length
    Vol_fuel = 0  # fuel volume
    mass = 0  # fuel mass
    A_fuel = 0  # fuel cross-sectional area
    A_flow = 0  # flow cross-sectional area
    fuel_frac = 0.75  # number of required fuel channels for given flow conditions
    
    core_r = 1 # guess core radius
    # flow parameters
    D_e = 0  # hydraulic diameter
    v = 0  # flow velocity
    dp = 0  # channel pressure drop

    # heat transfer attributes
    h_bar = 0  # average heat transfer coefficient
    f = 0  # friction factor

    # heat generation
    q_bar = 0  # axially-averaged volumetric generation
    q_per_channel = 0  # generation per fuel channel

    iterations = 0

    def __init__(self, cool_r, c, AR, power, fuel, cool, flowprops):
        """Initialize the flow iteration class.

        Initialized Attributes:
        --------------------
            r_channel: radius of coolant channel [m]
            c: cladding thickness [m]
            pitch: fuel thickness (minor axis of hexagon) [m]
            L: length of core [m]
        """
        self.Q_therm = power
        self.fuel = fuel
        self.coolant = cool
        self.fuelprops = phys_props[fuel]
        self.reflprops = phys_props['Carbon']
        self.cladprops = phys_props['Inconel-718']
        self.AR = AR
        self.c = c
        self.r_channel = cool_r
        # set up geometry
        self.set_geom()
        self.fps = flowprops
        self.dT = self.fuelprops['T_center'] - self.fps.T  # temp. drop fuel -> coolant

    def set_geom(self):
        """Setup the problem geometry.

        Modified Attributes:
        --------------------
            A_flow: flow area per fuel channel. [m^2]
            A_fuel: fuel area per fuel channel. [m^2]
            D_e: equivalent flow diameter [m]
        """
        self.A_core = self.core_r**2 * math.pi 
        self.A_flow = self.A_core * (1 - self.fuel_frac)
        self.A_fuel = self.A_core * self.fuel_frac
        
        self.L = self.AR * self.core_r
        self.LD = self.L / (self.r_channel*2)
        self.vol_fuel = self.A_fuel * self.L
        self.vol_cool = self.A_flow * self.L

        self.N_channels = self.A_flow / (self.r_channel**2 * math.pi)
        self.radius_cond = math.sqrt(self.A_fuel / self.N_channels) / 2
        self.XS_A_cond = math.pi * self.r_channel * self.L * 2 * self.N_channels
        
        # hydraulic diametre
        self.D_e = 2.0 * self.r_channel

    def characterize_flow(self):
        """Calculate important non-dim and dim flow parameters. These parameters
        are required to determine generation per fuel channel.

        Correlations and equations used are from El-Wakil's Nuclear Heat
        Transport Textbook

        Modified Attributes:
        --------------------
            v: flow velocity [m/s]
            f: friction factor [-]
            h_bar: heat transfer coefficient [W/m^2-K]
        """
        # roughness of cladding
        self.rough = self.cladprops['rough']
        # relative roughness
        self.relrough = self.rough / (self.r_channel*2)
        # calculate mass flux
        G_dot = self.fps.m_dot / self.A_flow
        # calculate flow velocity from mass flux
        self.v = G_dot / self.fps.rho
        # calculate Reynolds Number
        self.Re = self.fps.rho * self.v * self.D_e / self.fps.mu
        # Dittus-Boelter equation (9-22) from El-Wakil
        self.Nu, Nu_H, self.f = pipeflow_nd(self.Re, self.fps.Pr, self.LD, self.relrough)
        # heat transfer coefficient
        self.h_bar = self.Nu * self.fps.k_cool / self.D_e

    def get_q_per_channel(self):
        """Calculate achievable average volumetric generation:
        This method uses previously set geometry and calculated flow
        parameters to determine the maximum-achievable volumetric generation
        for each fuel channel. Calculates number of fuel channels required
        for desired thermal output.

        This method uses an equation from El-Wakil's Nuclear Heat Transport
        textbook.

        Modified Attributes:
        --------------------
            R_fuel: resistance term (conduction in the fuel) [W/K]
            R_clad: resistance term (conduction in the clad) [W/K]
            R_conv: resistance term (convection to the fluid) [W/K]
            R_tot: total resistance to HT [W/K]
            q_per_channel: total generation in fuel channel [W]
            q_bar: axially-averaged volumetric generation in fuel [W]
            N_channels: required channels for desired Q [-]
        """

        self.R_cond = self.radius_cond / (self.fuelprops['k_fuel'] * self.XS_A_cond)
        self.R_conv = 1 / (self.h_bar * self.r_channel * 2 * math.pi * self.L * self.N_channels)
        
        # calculate centerline volumetric generation
        q_trip_max = self.dT / (self.R_cond + self.R_conv)

        # consider axial flux variation
        self.gen_Q = q_trip_max * 2 / math.pi


    def calc_dp(self):
        """Calculate axial pressure drop across the reactor core.

        Modified Attributes:
        --------------------
            dp: core pressure drop [Pa]
        """
        # Darcy pressure drop (El-Wakil 9-3)
        self.dp = self.f * self.L * self.fps.rho * \
            self.v * self.v / (2*self.D_e)

    def adjust_dp(self):
        """Check for pressure constraint. This method calls calc_dp() to get
        the pressure drop in the current condition. It checks the dp against the
        power cycle-constrained allowable dp. If the pressure is too high, it
        adjusts N_channels to the min N_channels that satisfies the dp
        constraint.

        Modified Attributes:
        --------------------
            guess_channels: guess number of fuel channels [-]
            N_channels: number of fuel channels [-]
        """

        self.calc_dp()
        while self.dp > self.fps.dp_limit:
            # set N_channels and guess_channels
            self.N_channels = self.get_dp_constrained_Nchannels()
            self.characterize_flow()
            self.calc_dp()

    def get_dp_constrained_Nchannels(self):
        """Set the N_channels based on the allowable dP. This method
        calculates the required number of channels to meet the pressure drop
        constraint (set by the power cycle).

        Arguments:
        ----------
            self: Flow object [-]
        Returns:
        --------
            req_channels: Min N_channels required to meet dp constraint [-].
        """
        v_req = math.sqrt(2*self.D_e * self.fps.dp_limit /
                          (self.f * self.L * self.fps.rho))
        req_channels = math.ceil(
            self.fps.m_dot / (self.A_flow * self.fps.rho * v_req))

        return req_channels

    def compute_Q_from_guess(self, inp_guess):
        """Perform single 1D heat flow calculation. This method calls the
        required methods to perform one iteration of the calculation.

            Arguments:
            ----------
                inp_guess: (int) guess value for number of fuel channels
            Returns:
            --------
                error: (float) squared error between guess value for N_channels
                and the calculate N_channels
        """

        self.fuel_frac = inp_guess
        self.constrain_radius() 
        self.set_geom()
        self.characterize_flow()
        self.get_q_per_channel()
        
        return (self.gen_Q - self.Q_therm)**2

    def calc_reactor_mass(self):
        """Based on results of the iteration, calculate the reactor mass.

        Modified Attributes:
        --------------------
            Vol_fuel: total fuel volume [m^3]
            mass: total fuel mass[kg]
        """
        fuel_mass = self.vol_fuel * self.fuelprops['rho_fuel']
        cool_mass = self.vol_cool * self.fps.rho
        refl_mass = ((self.core_r * 1.05)**2 - self.core_r**2) *\
                     self.L * self.reflprops['rho']
        
        self.mass = fuel_mass + cool_mass + refl_mass 
    
    def constrain_radius(self):
        """Constrain the core radius based on criticality requirements.
        """

        coeffs = { 'UO2' : {'CO2' : (0.16271, -0.8515),
                            'H2O' : (0.1706,  -0.61361)
                           },

                   'UW'  : {'CO2' : (0.15385, -0.8309),
                            'H2O' : (0.16270, -0.6487)
                           }
                 }
        
        self.core_r = coeffs[self.fuel][self.coolant][0] *\
                      math.pow(self.fuel_frac, 
                               coeffs[self.fuel][self.coolant][1])
