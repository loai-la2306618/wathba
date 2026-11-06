"""Explain temporal movement comparison using measured evidence, not an LLM."""
import numpy as np
from .assessment import FEATURES, align_curves, waveform


def motion_analysis(session, reference=None):
    cycles = session.get('cycles', [])
    samples = session.get('samples', [])
    comparable = bool(reference and cycles and session.get('coverage', 0) >= 70)
    repetitions = []
    for c in cycles:
        features = []
        if comparable:
            for name, template in reference['templates'].items():
                observed = waveform(samples, c, name)
                if observed is None:
                    features.append({'name': name, 'label': FEATURES[name].label, 'available': False,
                                     'reason': 'Too few reliable observations in this repetition.'})
                    continue
                expected = np.asarray(template['median'])
                path = align_curves(expected, observed)
                delta = np.abs(expected[path[:, 0]] - observed[path[:, 1]])
                allowed = np.maximum(3 * np.asarray(template['spread'])[path[:, 0]], template['tolerance'])
                features.append({'name': name, 'label': FEATURES[name].label, 'available': True,
                                 'unit': FEATURES[name].unit, 'comparison_tolerance': template['tolerance'],
                                 'mean_difference': round(float(np.mean(delta)), 4),
                                 'outside_tolerance_pct': round(float(np.mean(delta > allowed) * 100), 1),
                                 'observed_excursion': round(float(np.ptp(observed)), 4),
                                 'reference_excursion': round(float(template['excursion_median']), 4),
                                 'observed_curve': np.round(observed, 5).tolist(),
                                 'reference_curve': np.round(expected, 5).tolist()})
        repetitions.append({'rep': c['rep'], 'start': c['start'], 'end': c['end'],
                            'duration': c['duration'],
                            'outward_seconds': round(c['peak_time'] - c['start'], 3),
                            'return_seconds': round(c['end'] - c['peak_time'], 3),
                            'excursion': c['excursion'], 'features': features})
    def variability(key):
        values = np.asarray([c[key] for c in cycles], dtype=float)
        if len(values) < 2 or float(np.mean(values)) <= 0:
            return None
        return round(float(np.std(values) / np.mean(values) * 100), 1)
    duration = float(np.median([c['duration'] for c in cycles])) if cycles else None
    return {'version': 'motion-evidence-v1', 'comparison_available': comparable,
            'reason': 'Reference comparison with separate timing and aligned movement features.' if comparable else
                      'A compatible reference and at least 70% trackable samples are needed for feature comparison.',
            'median_duration': round(duration, 3) if duration is not None else None,
            'reference_duration': reference['duration_median'] if comparable else None,
            'tempo_variation_pct': variability('duration'),
            'excursion_variation_pct': variability('excursion'),
            'repetitions': repetitions,
            'interpretation': 'Variation is the coefficient of variation across complete observed repetitions. '
                              'Feature differences are 2D estimates after temporal alignment, not clinical severity. '
                              'Pelvic excursion is not knee flexion range. The camera does not measure weight distribution, '
                              'ligament healing, pain, or exercise safety.'}


def session_analysis(session):
    """Also explain older saved sessions without changing their original measurements."""
    from . import storage
    reference = None
    ref_id = session.get('plan', {}).get('reference_id')
    if ref_id:
        try:
            reference = storage.load_reference(ref_id)
        except (OSError, ValueError):
            pass
    return motion_analysis(session, reference)
