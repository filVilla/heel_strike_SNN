# FUNZIONI CONDIVISE 
# Cosa fa: contatti() trova gli istanti di contatto del tallone dalla forza (soglia 0.5 V, picco >= 2 V,
#          durata >= 40 ms, pezzi a meno di 0.2 s uniti); omega_sagittale() ricava la velocita' angolare
#          della gamba nel piano avanti-indietro, qualunque sia il montaggio del sensore.


import numpy as np


def contatti(t, forza, soglia=0.5, picco=2.0, min_contatto=0.04, unisci=0.2):
    """Istanti (s) di inizio e fine dei contatti del tallone. Un contatto e' un tratto con la forza sopra
    `soglia` (V) che arriva ad almeno `picco` (V) e dura almeno `min_contatto` (s). La forza puo' scendere
    sotto soglia a meta' appoggio: i pezzi separati da meno di `unisci` (s) sono un solo contatto, che
    parte dalla prima salita. Gli istanti sono interpolati linearmente sulla soglia."""
    sopra = forza >= soglia
    salite = np.where(~sopra[:-1] & sopra[1:])[0] + 1
    discese = np.where(sopra[:-1] & ~sopra[1:])[0] + 1
    # Solo tratti completi: una discesa dopo ogni salita
    discese = discese[discese > salite[0]] if len(salite) else discese
    n = min(len(salite), len(discese))

    uniti = []
    for a, b in zip(salite[:n], discese[:n]):
        if uniti and t[a] - t[uniti[-1][1]] < unisci:
            uniti[-1][1] = b
        else:
            uniti.append([a, b])

    def su_soglia(i):
        f0, f1 = forza[i - 1], forza[i]
        return t[i - 1] + (soglia - f0) / (f1 - f0) * (t[i] - t[i - 1])

    inizi, fini = [], []
    for a, b in uniti:
        if forza[a:b].max() >= picco and t[b] - t[a] >= min_contatto:
            inizi.append(su_soglia(a))
            fini.append(su_soglia(b))
    return np.array(inizi), np.array(fini)


def omega_sagittale(gyr, inizi, t):
    """Velocita' angolare (°/s) attorno all'asse principale di rotazione: la prima componente
    principale del giroscopio (N, 3), che nel cammino e' l'asse del piano sagittale. Non dipende da come
    e' montato il sensore. Segno scelto in modo che sia positivo nei 160 ms prima di ogni contatto
    (fine del volo), cosi' prove diverse hanno lo stesso verso anche se cambia il picco piu' alto."""
    _, _, vt = np.linalg.svd(gyr - gyr.mean(axis=0), full_matrices=False)
    w = gyr @ vt[0]
    prima = [w[(t >= e - 0.16) & (t < e)].mean() for e in inizi if e - 0.16 >= t[0]]
    fine_volo = np.mean(prima) if prima else w.max() + w.min()
    return w if fine_volo >= 0 else -w


def acc_tibia(acc, gyr, inizi, fini, t):
    """Accelerazione (m/s², gravita' compresa) lungo due assi solidali alla tibia, qualunque sia il
    montaggio del sensore: verticale (verso il ginocchio, ~+9.8 da fermi) e sagittale (in avanti).
    Asse medio-laterale m = asse di rotazione di omega_sagittale(); verticale v = direzione media
    della gravita' col tallone a terra, resa perpendicolare a m; sagittale = v x m (in avanti perche'
    a fine volo, omega > 0, la caviglia avanza). Restituisce (verticale, sagittale)."""
    w = omega_sagittale(gyr, inizi, t)
    _, _, vt = np.linalg.svd(gyr - gyr.mean(axis=0), full_matrices=False)
    m = vt[0] if (gyr @ vt[0]) @ w >= 0 else -vt[0]
    terra = np.zeros(len(t), dtype=bool)
    for a, b in zip(inizi, fini):
        terra |= (t >= a) & (t <= b)
    g = acc[terra].mean(axis=0) if terra.any() else acc.mean(axis=0)
    v = g - (g @ m) * m
    v /= np.linalg.norm(v)
    return acc @ v, acc @ np.cross(v, m)
