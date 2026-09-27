"""Conservative feedback from measured quality and similarity only."""
from . import scoring


def diagnostics(measurements, gate, baseline=None, search=None):
    if not gate.valid:
        values = {
            'insufficient_hand_visibility': ('HANDS_NOT_VISIBLE', 1 - measurements.hand_visibility),
            'incomplete_sequence': ('TOO_FEW_FRAMES', 1 - min(measurements.sequence_completeness / scoring.MIN_SEQUENCE_COMPLETENESS, 1)),
            'insufficient_motion': ('MOTION_NOT_DETECTED', 1 - max(measurements.motion_energy / scoring.MIN_MOTION_ENERGY, measurements.motion_span / scoring.MIN_MOTION_SPAN)),
        }
        return [{'code': values[r][0], 'severity': float(max(0, min(1, values[r][1])))} for r in gate.reasons[:2]]
    if baseline.accepted:
        return []
    result = [{'code': 'LOW_MATCH', 'severity': 1 - baseline.score / 100}]
    if search['best_other_similarity'] > search['target_similarity']:
        result.append({'code': 'NEAREST_CONFUSION', 'severity': min(1, (search['best_other_similarity'] - search['target_similarity']) / 2)})
    return result
