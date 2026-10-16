"""Export identified contacts/resonator into a deterministic C++ model header."""
import argparse,json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser()
parser.add_argument('events')
parser.add_argument('--output',default='Source/ReferenceModel.h')
args=parser.parse_args()
m=json.loads(Path(args.events).read_text())
assert max(abs(np.roots(m['a'])))<1, 'Unstable identified resonator'
widths=[1,2,4,8,16]
header='''#pragma once
#include <array>
// Identified passive resonator and fitted contact-force trajectory.
// These are model coefficients/events, not PCM samples. See tools/MODEL.md.
namespace whoopee_model {
struct Contact { int time, width; double force; };
inline constexpr double rate = 8000.0;
inline constexpr int sourceLength = 6382;
inline constexpr std::array<double, 9> denominator {'''+','.join(f'{v:.17g}' for v in m['a'])+'''};
inline constexpr std::array<Contact, '''+str(len(m['events']))+'''> contacts {{
'''
for i,t,w in sorted(m['events'],key=lambda v:v[1]):
 width=widths[i]
 normalizer=sum(np.sin(np.pi*(np.arange(width)+.5)/width))
 force=w/m['kernel_norms'][i]/normalizer
 header+=f'    {{{t}, {width}, {force:.17g}}},\n'
header+='}};\n}\n'
Path(args.output).write_text(header)
