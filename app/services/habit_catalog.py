"""Versioned, bounded behavior recipes shared by media review and runtimes."""
SCHEMA = 1
LABELS = dict(recall='呼唤回应', greeting='欢迎方式', play='玩具互动', rest='休息习惯', activity='活动节奏', voice='原声回应')
RECIPES = {
    'recall': {'observe_come': ('先观察，再走近', ['curious', 'come', 'sit']),
               'come_sniff': ('走近后闻一闻', ['come', 'sniff'])},
    'greeting': {'sit': ('走近并坐下', ['come', 'sit']),
                 'sniff': ('走近并嗅闻', ['come', 'sniff']),
                 'affection': ('走近亲昵回应', ['come', 'affection'])},
    'play': {'sniff_first': ('先嗅闻再邀请玩耍', ['sniff', 'play_bow']),
             'invite': ('主动邀请玩耍', ['play_bow'])},
    'rest': {'sit': ('安静坐下', ['sit']), 'lie': ('趴下来休息', ['lie_down'])},
    'activity': {'calm': ('较慢、较少走动', []), 'lively': ('较活跃地探索', [])},
    'voice': {'greeting': ('重逢时播放原声', []), 'comfort': ('陪伴时播放原声', []), 'play': ('玩耍时播放原声', [])},
}
# A visible event suggests a draft only. No model output can invent an action.
OBSERVED = {'approach_sit': ('greeting', 'sit'), 'approach_sniff': ('greeting', 'sniff'),
            'sniff_object': ('play', 'sniff_first'), 'play_bow': ('play', 'invite'),
            'sit': ('rest', 'sit'), 'lie': ('rest', 'lie'),
            'walk': ('activity', 'lively'), 'still': ('activity', 'calm')}


def options():
    return {kind: {key: dict(label=label, plan=plan) for key, (label, plan) in recipes.items()}
            for kind, recipes in RECIPES.items()}


def valid(kind, value):
    return isinstance(kind, str) and isinstance(value, str) and value in RECIPES.get(kind, {})
