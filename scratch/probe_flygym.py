import time, numpy as np
from flygym import Simulation
from flygym.anatomy import BodySegment, ContactBodiesPreset
from flygym.compose import FlatGroundWorld
from flygym.utils.math import Rotation3D
from flygym.utils.mjcf import GEOM_TYPES
from flygym_demo.complex_terrain import (HybridTurningController, HybridControllerObservation,
    LocomotionAction, PreprogrammedSteps, apply_locomotion_action, make_locomotion_fly)
fly = make_locomotion_fly(name="fly", add_adhesion=True)
fly.add_vision()
world = FlatGroundWorld()
world.mjcf_root.worldbody.add_geom(type=GEOM_TYPES["cylinder"], name="pillar", pos=(10, 4, 3), size=(1.0, 3.0, 0), rgba=(0.05,0.05,0.05,1), contype=0, conaffinity=0)
world.add_fly(fly, [0,0,0.8], Rotation3D("quat",[1,0,0,0]), bodysegs_with_ground_contact=ContactBodiesPreset.TIBIA_TARSUS_ONLY, add_ground_contact_sensors=False)
sim = Simulation(world); print("timestep", sim.timestep)
steps = PreprogrammedSteps(); order = fly.get_actuated_jointdofs_order("position")
ctrl = HybridTurningController(timestep=sim.timestep, preprogrammed_steps=steps, output_dof_order=order)
sim.reset(); ctrl.reset(seed=0)
apply_locomotion_action(sim, fly.name, LocomotionAction(joint_angles=steps.default_pose_by_dof_order(order), adhesion_onoff=np.ones(6,bool)))
sim.warmup()
t=time.perf_counter(); r=sim.get_ommatidia_readouts(fly.name); print("vision", r.shape, r.dtype, "render ms", (time.perf_counter()-t)*1000)
t=time.perf_counter(); r=sim.get_ommatidia_readouts(fly.name); print("render ms (2nd)", (time.perf_counter()-t)*1000)
b = r.max(axis=2); print("mean brightness L,R", b.mean(1), "min L,R", b.min(1))
th = fly.get_bodysegs_order().index(BodySegment("c_thorax"))
p0 = sim.get_body_positions(fly.name)[th].copy(); t=time.perf_counter()
n=int(0.5/sim.timestep)
for i in range(n):
    obs = HybridControllerObservation.from_sim(sim, fly.name)
    apply_locomotion_action(sim, fly.name, ctrl.step(np.array([1.2,0.4]), obs)); sim.step()
p1 = sim.get_body_positions(fly.name)[th]; print("0.5s physics wall s", time.perf_counter()-t, "disp [1.2,0.4]:", np.round(p1-p0,3), "heading", np.round(obs.fly_heading,3))
