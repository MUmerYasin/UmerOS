# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import sys
import importlib.util

# [FIX H262] Resolve the target module relative to the project root instead of a
# hardcoded "UmerOS\quantum\..." path, which doubled up when the cwd already was
# the project root (FileNotFoundError: UmerOS\UmerOS\quantum\...).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TARGET = os.path.join(_PROJECT_ROOT, "quantum", "dynamic_circuits_v2.py")
spec = importlib.util.spec_from_file_location(
    'umerOS.quantum.dynamic_circuits_v2',
    _TARGET
)
mod = importlib.util.module_from_spec(spec)
sys.modules['umerOS.quantum.dynamic_circuits_v2'] = mod
spec.loader.exec_module(mod)

# ClassicalRegister
cr = mod.ClassicalRegister('c', 4)
cr.set_bit(0, 1); cr.set_bit(3, 1)
assert cr.to_int() == 9 and len(cr) == 4
cr2 = mod.ClassicalRegister.from_int(5, 3, name='d')
assert cr2.to_int() == 5

# ClassicalBit
cb = mod.ClassicalBit(index=0, register='c', value=1)
assert 'ClassicalBit' in repr(cb)

# DCClassicalCondition
cond = mod.DCClassicalCondition(bit_index=0, register='c', comparison='==', value=1)
assert cond.evaluate(cr) is True
assert mod.DCClassicalCondition(0, 'c', '!=', 0).evaluate(cr) is True
assert mod.DCClassicalCondition(0, 'c', '>', 0).evaluate(cr) is True
assert mod.DCClassicalCondition(0, 'c', '<', 0).evaluate(cr) is False
assert mod.DCClassicalCondition(0, 'c', '>=', 1).evaluate(cr) is True
assert mod.DCClassicalCondition(0, 'c', '<=', 1).evaluate(cr) is True
d = cond.to_dict()
cond2 = mod.DCClassicalCondition.from_dict(d)
assert cond2.bit_index == 0 and cond2.comparison == '=='

# ClassicalOperation (all 6 ops)
bv_and = {('c', 0): 1, ('c', 1): 1}
bv_or = {('c', 0): 1, ('c', 1): 0}
bv_xor = {('c', 0): 1, ('c', 1): 1}
bv_not = {('c', 0): 1}
bv_nand = {('c', 0): 1, ('c', 1): 1}
bv_nor = {('c', 0): 0, ('c', 1): 0}

assert mod.ClassicalOperation('NOT', [('c', 0)], ('d', 0)).evaluate(bv_not) == 0
assert mod.ClassicalOperation('AND', [('c', 0), ('c', 1)], ('d', 0)).evaluate(bv_and) == 1
assert mod.ClassicalOperation('AND', [('c', 0), ('c', 1)], ('d', 0)).evaluate(bv_or) == 0
assert mod.ClassicalOperation('OR', [('c', 0), ('c', 1)], ('d', 0)).evaluate(bv_or) == 1
assert mod.ClassicalOperation('XOR', [('c', 0), ('c', 1)], ('d', 0)).evaluate(bv_xor) == 0
assert mod.ClassicalOperation('NAND', [('c', 0), ('c', 1)], ('d', 0)).evaluate(bv_nand) == 0
assert mod.ClassicalOperation('NOR', [('c', 0), ('c', 1)], ('d', 0)).evaluate(bv_nor) == 1

# MidCircuitMeasurement
mcm = mod.MidCircuitMeasurement(qubit=0, classical_bit=0, basis='Z')
d = mcm.to_dict()
mcm2 = mod.MidCircuitMeasurement.from_dict(d)
assert mcm2.qubit == 0
mcm_c = mod.MidCircuitMeasurement(qubit=1, classical_bit=1, basis='X', condition_on=cond)
assert mcm_c.to_dict()['condition_on'] is not None

# ConditionalGate
cg = mod.ConditionalGate(gate_name='X', target_qubits=[1], condition=cond)
assert 'ConditionalGate' in repr(cg)
cg_p = mod.ConditionalGate(gate_name='RZ', target_qubits=[0], condition=cond, params={'theta': 1.57})
assert cg_p.params['theta'] == 1.57

# DCWhileLoop
wl = mod.DCWhileLoop(condition=cond, max_iterations=10)
assert wl.to_dict()['max_iterations'] == 10
assert 'DCWhileLoop' in repr(wl)

# SwitchCase
sc = mod.SwitchCase(classical_bit_index=0, register='c', cases={0: ['a'], 1: ['b']}, default=['c'])
assert sc.get_branch(1) == ['b']
assert sc.get_branch(5) == ['c']
sd = sc.to_dict()
assert sd['cases']['0'] == [repr('a')]
assert sd['default'] == [repr('c')]

# FeedforwardController
ffc = mod.FeedforwardController()
ffc.add_condition(qubit=1, classical_bit=0, operation='X')
ffc.add_condition(qubit=2, classical_bit=0, operation='Z', comparison='==', value=0)
assert len(ffc) == 2
assert len(ffc.get_all_conditions()) == 2

# is_dynamic_capable
for name in ['ibm_brisbane', 'IBM_Brisbane', 'quantinuum_h1', 'ionq_harmony', 'ionq_forte']:
    assert mod.is_dynamic_capable(name)
assert not mod.is_dynamic_capable('unknown_backend')

# utility functions
bell = mod.create_bell_pair_with_condition()
assert bell['type'] == 'bell_pair_with_condition' and bell['num_qubits'] == 2
bf = mod.create_bit_flip_detection()
assert bf['type'] == 'bit_flip_detection' and bf['num_qubits'] == 5
tp = mod.create_teleportation_circuit()
assert tp['type'] == 'teleportation' and tp['num_qubits'] == 3

# estimate_classical_processing_overhead
fake_circuit_for_overhead = type('FakeCircuit', (), {
    'mid_circuit_measurements': [mcm] * 3,
    'conditional_gates': [cg] * 2,
    'classical_registers': [cr],
    'num_qubits': 2, 'num_clbits': 4
})()
ov = mod.estimate_classical_processing_overhead(fake_circuit_for_overhead)
assert ov['num_mid_circuit_measurements'] == 3
assert ov['num_conditional_gates'] == 2

# compiler
comp = mod.DynamicCircuitCompiler(backend='ibm')
fake_circuit = type('FakeCircuit', (), {
    'mid_circuit_measurements': [], 'conditional_gates': [],
    'classical_registers': [], 'num_qubits': 2, 'num_clbits': 2
})()
compiled = comp.compile(fake_circuit)
assert compiled['backend'] == 'ibm'
assert compiled['supports_dynamic'] is True
assert 'native_gates' in compiled

# compiler estimate_resource_overhead
fake_dc = type('FakeDC', (), {
    'mid_circuit_measurements': [mcm], 'conditional_gates': [cg],
    'classical_registers': [], 'num_qubits': 2, 'num_clbits': 2
})()
overhead = comp.estimate_resource_overhead(fake_dc)
assert overhead['num_mid_circuit_measurements'] == 1
assert overhead['num_conditional_gates'] == 1

# DynamicCircuitExecutor
class FakeProvider:
    name = 'test_backend'
    def run(self, circuit, shots):
        return {'counts': {'00': 512, '11': 512}}

ex = mod.DynamicCircuitExecutor(FakeProvider())
res = ex.execute(None, shots=1024)
assert res['total_shots'] == 1024
assert res['counts'] == {'00': 512, '11': 512}

# Error handling
try:
    cr.set_bit(0, 2)
    assert False
except ValueError:
    pass

try:
    mod.DCClassicalCondition(0, 'c', 'XOR', 1)
    assert False
except ValueError:
    pass

try:
    mod.MidCircuitMeasurement(qubit=-1, classical_bit=0)
    assert False
except ValueError:
    pass

try:
    mod.MidCircuitMeasurement(qubit=0, classical_bit=0, basis='W')
    assert False
except ValueError:
    pass

try:
    mod.ClassicalOperation(operation='BAD', input_bits=[], output_bit=('c', 0))
    assert False
except ValueError:
    pass

try:
    mod.ClassicalBit(index=0, register='c', value=2)
    assert False
except ValueError:
    pass

try:
    mod.ClassicalRegister('c', 0)
    assert False
except ValueError:
    pass

try:
    mod.DCWhileLoop(condition=cond, max_iterations=-1)
    assert False
except ValueError:
    pass

try:
    cr.get_bit(99)
    assert False
except IndexError:
    pass

try:
    mod.ClassicalRegister.from_int(100, 2)
    assert False
except ValueError:
    pass

try:
    mod.DynamicCircuitExecutor(None)
    assert False
except ValueError:
    pass

fresh = mod.ClassicalRegister('x', 2)
try:
    mod.DCClassicalCondition(0, 'x', '==', 1).evaluate(fresh)
    assert False
except ValueError:
    pass

try:
    mod.ClassicalOperation('AND', [('c', 0), ('c', 1)], ('d', 0)).evaluate({('c', 0): 1})
    assert False
except KeyError:
    pass

print('All 50+ tests passed!')
