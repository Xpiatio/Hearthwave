NICKNAMES: dict[str, frozenset[str]] = {
    # William family
    "bill": frozenset({"william"}),
    "billy": frozenset({"william"}),
    "will": frozenset({"william"}),
    "willy": frozenset({"william"}),
    "liam": frozenset({"william"}),
    # Robert
    "bob": frozenset({"robert"}),
    "bobby": frozenset({"robert"}),
    "rob": frozenset({"robert"}),
    "robby": frozenset({"robert"}),
    # Richard
    "dick": frozenset({"richard"}),
    "rick": frozenset({"richard"}),
    "ricky": frozenset({"richard"}),
    # James
    "jim": frozenset({"james"}),
    "jimmy": frozenset({"james"}),
    "jamie": frozenset({"james"}),
    # John
    "jack": frozenset({"john"}),
    "johnny": frozenset({"john"}),
    # Henry
    "hank": frozenset({"henry"}),
    "harry": frozenset({"henry", "harold"}),
    # Charles
    "chuck": frozenset({"charles"}),
    "chuckie": frozenset({"charles"}),
    "charlie": frozenset({"charles"}),
    # Michael
    "mike": frozenset({"michael"}),
    "mikey": frozenset({"michael"}),
    "mickey": frozenset({"michael"}),
    # Edward / Edmund
    "ed": frozenset({"edward", "edmund"}),
    "eddie": frozenset({"edward", "edmund"}),
    "ted": frozenset({"edward", "theodore"}),
    "teddy": frozenset({"edward", "theodore"}),
    "ned": frozenset({"edward", "edmund"}),
    # Theodore
    "theo": frozenset({"theodore"}),
    # Anthony
    "tony": frozenset({"anthony"}),
    # Arthur
    "art": frozenset({"arthur"}),
    "artie": frozenset({"arthur"}),
    # Lawrence / Laurence
    "larry": frozenset({"lawrence", "laurence"}),
    # Frederick / Alfred
    "fred": frozenset({"frederick", "alfred"}),
    "freddy": frozenset({"frederick", "alfred"}),
    # Francis / Franklin
    "frank": frozenset({"francis", "franklin"}),
    "frankie": frozenset({"francis", "franklin"}),
    # Nicholas
    "nick": frozenset({"nicholas"}),
    "nicky": frozenset({"nicholas"}),
    # Joseph
    "joe": frozenset({"joseph"}),
    "joey": frozenset({"joseph"}),
    # Daniel
    "dan": frozenset({"daniel"}),
    "danny": frozenset({"daniel"}),
    # Ronald
    "ron": frozenset({"ronald"}),
    "ronnie": frozenset({"ronald"}),
    # Stephen / Steven
    "steve": frozenset({"steven", "stephen"}),
    "stevie": frozenset({"steven", "stephen"}),
    # Christopher (also Christina / Christine — ambiguous but acceptable)
    "chris": frozenset({"christopher", "christina", "christine"}),
    # Gerald / Jerome
    "jerry": frozenset({"gerald", "jerome"}),
    # Alexander / Sandra
    "sandy": frozenset({"alexander", "sandra"}),
    "alex": frozenset({"alexander", "alexandra"}),
    "al": frozenset({"albert", "alfred", "alan", "alexander"}),
    # Vincent
    "vinny": frozenset({"vincent"}),
    "vince": frozenset({"vincent"}),
    # Patrick / Patricia
    "pat": frozenset({"patrick", "patricia"}),
    "patty": frozenset({"patrick", "patricia"}),
    "patsy": frozenset({"patrick", "patricia"}),

    # Female names — non-prefix nicknames where the existing prefix rule
    # in name_matches doesn't already cover the diminutive.
    "peggy": frozenset({"margaret"}),
    "meg": frozenset({"margaret"}),
    "maggie": frozenset({"margaret"}),
    "molly": frozenset({"mary"}),
    "polly": frozenset({"mary"}),
    "sally": frozenset({"sarah"}),
    "betty": frozenset({"elizabeth"}),
    "beth": frozenset({"elizabeth"}),
    "liz": frozenset({"elizabeth"}),
    "liza": frozenset({"elizabeth"}),
    "lisa": frozenset({"elizabeth"}),
    "betsy": frozenset({"elizabeth"}),
    "kate": frozenset({"katherine", "kathryn", "katelyn"}),
    "katie": frozenset({"katherine", "kathryn", "katelyn"}),
    "kat": frozenset({"katherine", "kathryn"}),
    "kathy": frozenset({"katherine", "kathryn"}),
    "ginny": frozenset({"virginia"}),
    "nancy": frozenset({"ann", "agnes"}),
    "sue": frozenset({"susan", "susanne"}),
    "suzie": frozenset({"susan", "susanne"}),
    "becky": frozenset({"rebecca"}),
    "penny": frozenset({"penelope"}),
    "terri": frozenset({"theresa", "teresa"}),
    "terry": frozenset({"theresa", "terrence"}),
    "trish": frozenset({"patricia"}),
}


def canonical_forms(token: str) -> frozenset[str]:
    lowered = (token or "").lower()
    if not lowered:
        return frozenset()
    canonicals = NICKNAMES.get(lowered)
    if canonicals is None:
        return frozenset({lowered})
    return canonicals | {lowered}
