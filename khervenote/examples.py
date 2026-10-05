# KherveNote — example notes for scientists
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later
"""Worked example notes — mathematics, physics, chemistry and materials
science — each a lecture with sections, lists, key points, questions,
equations and the speech that was heard beside it, so every feature can
be tried on something realistic.  Help ▸ Example notes copies them into
the library's Examples folder.

Each example is written in a small text form:

``# Title @mm:ss``  a section, written that long into the session
``## Title``        a subsection
``- item``          a bullet (indent two spaces per level); ``1. item`` numbered
``! text``          a key point;  ``? text`` a question
anything else      a paragraph; maths as $…$ or $$…$$
"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .knote_file import save_knote
from .library import safe_name
from .model import Block, Meta, Note, Section, Segment

FOLDER = "Examples"


@dataclass
class Example:
    title: str
    speaker: str
    place: str
    started: str                     # ISO time the session began
    body: str
    speech: list[tuple[str, str]] = field(default_factory=list)   # ("mm:ss", text)
    summary: str = ""


def _secs(stamp: str) -> float:
    m, s = stamp.split(":")
    return int(m) * 60 + int(s)


_SECTION = re.compile(r"^# (.+?)(?:\s+@(\d+:\d\d))?$")
_ITEM = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")


def build(ex: Example) -> Note:
    """The note an example describes."""
    started = datetime.fromisoformat(ex.started)
    note = Note(meta=Meta(title=ex.title, speaker=ex.speaker, place=ex.place,
                          date=started.strftime("%d %B %Y"), started=ex.started),
                summary=" ".join(ex.summary.split()), sections=[Section()])
    t = 0.0
    para: list[str] = []

    def add(block: Block) -> None:
        nonlocal t
        t += 25
        block.t = t
        note.sections[-1].blocks.append(block)

    def flush() -> None:
        if para:
            add(Block(kind="typed", text=" ".join(para)))
            para.clear()

    for raw in ex.body.strip().splitlines():
        line = raw.rstrip()
        sec = _SECTION.match(line)
        item = _ITEM.match(line)
        if not line.strip():
            flush()
        elif sec:
            flush()
            if sec.group(2):
                t = _secs(sec.group(2))
            note.sections.append(Section(title=sec.group(1).strip(), t=t))
        elif line.startswith("## "):
            flush()
            add(Block(kind="heading", text=line[3:].strip(), level=2))
        elif line.startswith("! "):
            flush()
            add(Block(kind="important", text=line[2:].strip()))
        elif line.startswith("? "):
            flush()
            add(Block(kind="question", text=line[2:].strip()))
        elif item:
            flush()
            add(Block(kind="item", text=item.group(3).strip(),
                      level=min(3, len(item.group(1)) // 2),
                      numbered=item.group(2)[0].isdigit()))
        else:
            para.append(line.strip())
    flush()
    if len(note.sections) > 1 and not note.sections[0].blocks:
        note.sections.pop(0)
    note.transcript = [Segment(_secs(stamp), text) for stamp, text in ex.speech]
    return note


def install(root: Path) -> list[Path]:
    """Write every example into ``<root>/Examples`` — never over a file
    that is already there, so edited examples are kept."""
    folder = Path(root) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    with tempfile.TemporaryDirectory() as work:
        for ex in EXAMPLES:
            path = folder / f"{safe_name(ex.title)}.knote"
            if not path.exists():
                save_knote(build(ex), path, Path(work))
            out.append(path)
    return out


# ── the examples ────────────────────────────────────────────────────

EXAMPLES = [
Example(
    "Linear algebra 7 — Eigenvalues and diagonalisation", "Lecturer: Dr A. Martin",
    "Maths building, Room 140", "2026-10-05T09:00:00",
    summary="""Eigenvectors are the directions a matrix only stretches; the eigenvalues
are the stretch factors, found from det(A − λI) = 0. A matrix with n independent
eigenvectors can be written A = PDP⁻¹, which makes powers and many applications easy.
Symmetric matrices always can, with an orthogonal P.""",
    body=r"""
# Eigenvalues and eigenvectors @02:00
A non-zero vector $\mathbf{v}$ is an eigenvector of a square matrix $A$ when
$$A\mathbf{v} = \lambda\mathbf{v}$$
for some scalar $\lambda$, its eigenvalue: $A$ only stretches $\mathbf{v}$, it does not turn it.
- eigenvectors are only defined up to a scale factor
- $\lambda = 0$ is allowed; then $A$ is singular
- the eigenvalues of a triangular matrix are its diagonal entries
! Sum of the eigenvalues = trace of $A$; product of the eigenvalues = $\det A$.

# The characteristic polynomial @09:30
$(A - \lambda I)\mathbf{v} = 0$ has a non-zero solution only if
$$\det(A - \lambda I) = 0$$
— a polynomial of degree $n$ in $\lambda$, so an $n \times n$ matrix has $n$ eigenvalues counted with multiplicity (possibly complex).
## Worked example
For $A = \begin{pmatrix} 2 & 1 \\ 1 & 2 \end{pmatrix}$: $\det(A-\lambda I) = (2-\lambda)^2 - 1 = (\lambda-3)(\lambda-1)$.
1. $\lambda_1 = 3$: $\mathbf{v}_1 = (1, 1)^T$
2. $\lambda_2 = 1$: $\mathbf{v}_2 = (1, -1)^T$
Check: trace $= 4 = 3 + 1$, det $= 3 = 3 \times 1$.
? What happens when an eigenvalue is repeated — are there always enough eigenvectors?

# Diagonalisation @21:00
If $A$ has $n$ linearly independent eigenvectors, put them as the columns of $P$ and the eigenvalues on the diagonal of $D$:
$$A = P D P^{-1}, \qquad A^k = P D^k P^{-1}$$
- distinct eigenvalues ⇒ independent eigenvectors ⇒ diagonalisable
- a repeated eigenvalue may give too few eigenvectors (a defective matrix, e.g. $\begin{pmatrix} 1 & 1 \\ 0 & 1 \end{pmatrix}$)
! Spectral theorem: a real symmetric matrix has real eigenvalues and orthonormal eigenvectors, so $A = Q D Q^T$ with $Q^{-1} = Q^T$.

# Applications @33:00
- Markov chains: the steady state is the eigenvector with $\lambda = 1$
- coupled oscillators: eigenvectors are the normal modes, eigenvalues give $\omega^2$
- principal component analysis: eigenvectors of the covariance matrix
- systems of ODEs $\dot{\mathbf{x}} = A\mathbf{x}$: solutions $e^{\lambda t}\mathbf{v}$
? Problem sheet 7, questions 3–6 for Friday.
""",
    speech=[
        ("00:40", "Good morning. Today is eigenvalues, probably the most useful idea in this course."),
        ("01:30", "An eigenvector is a direction the matrix doesn't rotate, it only stretches it, and the eigenvalue is how much."),
        ("05:10", "Note that if lambda is zero the matrix sends that vector to zero, so it can't be invertible."),
        ("07:45", "A quick check I always use: the eigenvalues add up to the trace and multiply to the determinant."),
        ("10:20", "To find them, we ask when A minus lambda I can send a non-zero vector to zero, that's when its determinant vanishes."),
        ("15:00", "For the two by two example we get lambda minus three times lambda minus one, so three and one."),
        ("19:40", "Now the big idea: if you have enough eigenvectors you can change basis so the matrix becomes diagonal."),
        ("24:30", "Powers become trivial, A to the k is P D to the k P inverse, you just raise the diagonal entries."),
        ("28:00", "Careful with repeated eigenvalues, the matrix one one zero one only has one eigenvector."),
        ("31:30", "Symmetric matrices are the nice case, real eigenvalues and orthogonal eigenvectors, that's the spectral theorem."),
        ("34:10", "In physics you will meet this as normal modes, in data science as principal components."),
    ]),

Example(
    "Quantum mechanics 4 — The particle in a box", "Lecturer: Prof. R. Okafor",
    "Physics lecture theatre 1", "2026-10-06T11:00:00",
    summary="""A particle confined to a box of width L can only have energies
Eₙ = n²h²/(8mL²): energy is quantised, the lowest level is not zero, and the
levels spread apart as the box shrinks — the origin of quantum confinement in
nanoparticles and quantum dots.""",
    body=r"""
# Setting up the problem @01:30
Potential $V = 0$ for $0 < x < L$ and $V = \infty$ outside: the particle cannot leave the box.
Inside, the time-independent Schrödinger equation is
$$-\frac{\hbar^2}{2m}\frac{d^2\psi}{dx^2} = E\psi$$
with boundary conditions $\psi(0) = \psi(L) = 0$.

# Solutions @08:00
- general solution $\psi = A\sin kx + B\cos kx$, with $k = \sqrt{2mE}/\hbar$
- $\psi(0) = 0 \Rightarrow B = 0$
- $\psi(L) = 0 \Rightarrow kL = n\pi$, $n = 1, 2, 3, \dots$
Normalised wavefunctions and energies:
$$\psi_n(x) = \sqrt{\tfrac{2}{L}}\,\sin\frac{n\pi x}{L}, \qquad E_n = \frac{n^2\pi^2\hbar^2}{2mL^2} = \frac{n^2 h^2}{8 m L^2}$$
! Energy is quantised by the boundary conditions alone, and $E_1 > 0$: zero-point energy, consistent with the uncertainty principle.
- $\psi_n$ has $n - 1$ nodes inside the box
- level spacing $E_{n+1} - E_n \propto 2n + 1$ grows with $n$
- probability density $|\psi_n|^2$ is not uniform; for large $n$ it averages to $1/L$ (correspondence principle)

# Numbers: an electron in a 1 nm box @20:00
$E_1 = h^2/(8 m_e L^2) = (6.626\times10^{-34})^2 / (8 \times 9.109\times10^{-31} \times 10^{-18}) \approx 6.0\times10^{-20}$ J $\approx 0.38$ eV.
- $E_2 = 4E_1 \approx 1.5$ eV, so the $1 \to 2$ transition is about 1.1 eV (in the near infrared)
- for a 1 g marble in a 1 cm box the spacing is immeasurably small — classical behaviour

# Quantum confinement in materials @29:00
$E \propto 1/L^2$: the smaller the box, the larger the gap.
- quantum dots (e.g. CdSe): smaller dots emit bluer light
- quantum wells in semiconductor lasers; conjugated molecules (free-electron model of polyenes)
? Why does a finite well always have at least one bound state, while the infinite one starts at n = 1?
""",
    speech=[
        ("00:50", "Today we solve our first real problem, a particle trapped in a box with infinitely high walls."),
        ("06:20", "Inside the box the potential is zero, so the Schrödinger equation is just the free particle one."),
        ("09:40", "The wavefunction has to vanish at both walls, and that's what forces the energy to come in steps."),
        ("14:30", "Notice the lowest energy is not zero. You cannot have a particle at rest in a box, that would violate uncertainty."),
        ("18:20", "Let's put numbers in for an electron in a box one nanometre wide."),
        ("21:40", "That gives about zero point four electronvolts for the ground state, so these are energies you can see with light."),
        ("27:10", "Now make the box smaller and the levels spread apart as one over L squared."),
        ("30:30", "This is exactly why small cadmium selenide quantum dots glow blue and larger ones red."),
    ]),

Example(
    "Thermodynamics 3 — The laws and entropy", "Lecturer: Dr S. Lindqvist",
    "Chemistry building, LT2", "2026-10-07T10:00:00",
    body=r"""
# The first law @01:00
Energy is conserved: $\Delta U = q + w$ (heat and work done *on* the system).
- at constant volume $\Delta U = q_V$; at constant pressure $\Delta H = q_p$, with $H = U + pV$
- state functions ($U$, $H$, $S$, $G$) depend only on the state, not the path; $q$ and $w$ do not

# Entropy and the second law @10:00
$$dS = \frac{\delta q_{\mathrm{rev}}}{T}, \qquad \Delta S_{\mathrm{universe}} \geq 0$$
Statistically, $S = k_B \ln W$ — the number of microstates.
## Worked example: melting ice
$\Delta H_{\mathrm{fus}} = 6.01$ kJ mol$^{-1}$ at 273.15 K, so $\Delta S_{\mathrm{fus}} = 6010 / 273.15 \approx 22.0$ J K$^{-1}$ mol$^{-1}$.
! Heat engines: no engine between $T_h$ and $T_c$ beats the Carnot efficiency $\eta = 1 - T_c/T_h$.

# Gibbs energy @24:00
At constant $T$ and $p$, the second law becomes a condition on the system alone:
$$G = H - TS, \qquad \Delta G = \Delta H - T\Delta S < 0 \text{ for a spontaneous change}$$
1. $\Delta H < 0$, $\Delta S > 0$: spontaneous at all $T$
2. $\Delta H > 0$, $\Delta S > 0$: spontaneous above $T = \Delta H / \Delta S$
3. $\Delta H < 0$, $\Delta S < 0$: spontaneous below $T = \Delta H / \Delta S$
4. $\Delta H > 0$, $\Delta S < 0$: never
- equilibrium: $\Delta G^\circ = -RT\ln K$

# The third law @36:00
The entropy of a perfect crystal tends to zero as $T \to 0$ K, which gives absolute entropies.
? How does residual entropy (e.g. in ice or CO) fit with the third law?
""",
    speech=[
        ("00:30", "Three laws today, and by the end you should be able to predict whether a reaction can go."),
        ("05:40", "Remember the sign convention, w is work done on the system, so compression is positive."),
        ("09:00", "Entropy: the classical definition is heat exchanged reversibly divided by temperature."),
        ("13:30", "Boltzmann's view is more intuitive, entropy counts the number of ways the system can be arranged."),
        ("18:10", "For melting ice, six point zero one kilojoules divided by two seven three gives about twenty-two joules per kelvin per mole."),
        ("22:00", "Now combine both into one quantity for the system at constant temperature and pressure, that's the Gibbs energy."),
        ("27:30", "When enthalpy and entropy have the same sign, temperature decides, and the crossover is delta H over delta S."),
        ("34:40", "Finally the third law, which sets the zero of entropy."),
    ]),

Example(
    "Chemical kinetics — Rate laws and the Arrhenius equation", "Lecturer: Dr M. Haddad",
    "Chemistry building, LT1", "2026-10-08T14:00:00",
    summary="""Rate laws are found by experiment, not from the balanced equation.
Integrated rate laws give straight-line plots that reveal the order; the
Arrhenius equation links the rate constant to the activation energy, and a
catalyst works by offering a path with a lower one.""",
    body=r"""
# Rate laws @01:00
For $aA + bB \rightarrow$ products, the rate is $r = -\frac{1}{a}\frac{d[A]}{dt} = k[A]^m[B]^n$.
! The orders $m$ and $n$ are measured; they need not equal $a$ and $b$.
- overall order $m + n$; units of $k$ depend on it
- method of initial rates: change one concentration, watch the initial rate

# Integrated rate laws @12:00
1. zero order: $[A] = [A]_0 - kt$; $t_{1/2} = [A]_0/(2k)$
2. first order: $\ln[A] = \ln[A]_0 - kt$; $t_{1/2} = \ln 2 / k$, independent of $[A]_0$
3. second order: $\dfrac{1}{[A]} = \dfrac{1}{[A]_0} + kt$; $t_{1/2} = 1/(k[A]_0)$
- plot $[A]$, $\ln[A]$ and $1/[A]$ against $t$: the straight one gives the order
- radioactive decay and many isomerisations are first order

# Temperature: the Arrhenius equation @24:00
$$k = A\exp\left(-\frac{E_a}{RT}\right), \qquad \ln k = \ln A - \frac{E_a}{R}\cdot\frac{1}{T}$$
A plot of $\ln k$ against $1/T$ has slope $-E_a/R$.
## Worked example
With $E_a = 50$ kJ mol$^{-1}$, going from 298 K to 308 K:
$\ln(k_2/k_1) = \frac{E_a}{R}\left(\frac{1}{T_1} - \frac{1}{T_2}\right) = \frac{50000}{8.314}\times 1.09\times10^{-4} \approx 0.66$, so $k_2/k_1 \approx 1.9$.
! The "rate doubles every 10 °C" rule of thumb holds for $E_a$ around 50 kJ mol$^{-1}$ near room temperature.

# Mechanisms @36:00
- elementary steps have orders equal to their molecularity
- the rate-determining step sets the rate law
- steady-state approximation for reactive intermediates: $d[I]/dt \approx 0$
- a catalyst lowers $E_a$ by a different path; it does not change $K$
? Why can a rate law contain the concentration of a species that is not in the overall equation?
""",
    speech=[
        ("00:40", "Kinetics is about how fast, thermodynamics only tells you whether."),
        ("04:20", "The big warning: you cannot read the orders off the balanced equation, you have to measure them."),
        ("10:30", "The easiest way to find the order is to integrate the rate law and see which plot comes out straight."),
        ("16:00", "For first order the half-life doesn't depend on how much you start with, that's the signature."),
        ("22:10", "Now temperature. Arrhenius noticed that log k against one over T is a straight line."),
        ("27:40", "Take fifty kilojoules per mole and warm by ten degrees, the rate constant almost doubles."),
        ("34:00", "Real reactions happen in steps, and the slowest step controls the overall rate."),
        ("38:20", "A catalyst gives a lower barrier, but the equilibrium constant stays exactly the same."),
    ]),

Example(
    "Surface analysis — X-ray photoelectron spectroscopy (XPS)", "Lecturer: Dr L. Moreau",
    "Materials building, LG11", "2026-10-09T09:30:00",
    summary="""XPS measures the binding energies of core electrons ejected by X-rays,
giving the elements present in the top few nanometres and their chemical
states. Peak positions shift with oxidation state; spin–orbit doublets have
fixed area ratios; quantification needs a background and sensitivity factors.""",
    body=r"""
# Principle @01:30
A photon of energy $h\nu$ ejects a core electron; we measure its kinetic energy:
$$E_B = h\nu - E_K - \phi_{\mathrm{sp}}$$
with $\phi_{\mathrm{sp}}$ the spectrometer work function.
- Al Kα (monochromated) 1486.6 eV; Mg Kα 1253.6 eV
- every element except H and He can be detected
! Surface sensitive: photoelectrons travel only ~1–3 nm (the inelastic mean free path λ) without losing energy, so ~95 % of the signal comes from within 3λ, i.e. the top ≈ 5–10 nm.

# Chemical shifts @10:00
The binding energy rises with the oxidation state (less electron density, less screening).
- Si 2p: Si⁰ ≈ 99.3 eV, SiO₂ ≈ 103.3 eV — about +4 eV
- C 1s: C–C ≈ 284.8 eV, C–O ≈ 286.5 eV, C=O ≈ 288 eV, O–C=O ≈ 289 eV
## Spin–orbit splitting
Levels with $l > 0$ split into doublets with fixed area ratios:
1. p: $p_{1/2} : p_{3/2} = 1 : 2$
2. d: $d_{3/2} : d_{5/2} = 2 : 3$
3. f: $f_{5/2} : f_{7/2} = 3 : 4$
- Au 4f₇/₂ = 84.0 eV, splitting 3.67 eV — a common calibration

# Peak fitting and quantification @22:00
- subtract a background first: Shirley (iterative, step-like), Tougaard (physical loss function) or linear
- fit components with Voigt / pseudo-Voigt shapes; constrain doublet ratios and splittings
- atomic fraction $x_i = \dfrac{I_i/S_i}{\sum_j I_j/S_j}$ with relative sensitivity factors $S$
! Accuracy is typically 10–20 % relative — report it with the fitting choices.

# Practical issues @33:00
- insulators charge positively: use a flood gun and reference the scale
- adventitious carbon C 1s at 284.8 eV is the usual reference, but it is debated
- sputtering for depth profiles can reduce oxides — beware of beam damage
? Is the adventitious carbon reference reliable on samples that were heated or sputtered?
""",
    speech=[
        ("00:50", "XPS is our workhorse for surfaces, so it's worth understanding where every number comes from."),
        ("05:30", "We use monochromated aluminium K alpha at fourteen eighty-six point six electronvolts."),
        ("08:10", "The electrons we count have only come from the top few nanometres, deeper ones lose energy on the way out."),
        ("12:40", "Oxidise silicon and the two p peak moves up by about four electronvolts, that's the chemical shift."),
        ("17:20", "For p, d and f levels you always get a doublet, and the area ratio is fixed by the degeneracy."),
        ("20:30", "Before fitting anything you need a background. Shirley is the common choice, Tougaard is more physical."),
        ("27:00", "Quantification divides each area by its sensitivity factor; don't expect better than ten or twenty percent."),
        ("31:40", "Insulating samples charge up, so we use the flood gun and reference to adventitious carbon."),
        ("35:10", "There's an ongoing debate on whether two eight four point eight is a good reference at all."),
    ]),

Example(
    "Crystallography — X-ray diffraction and crystal structure", "Lecturer: Dr K. Nakamura",
    "Materials building, Room 202", "2026-10-12T11:00:00",
    body=r"""
# Bragg's law @01:00
X-rays reflected from planes $d$ apart interfere constructively when
$$n\lambda = 2d\sin\theta$$
- Cu Kα: $\lambda = 1.5406$ Å (Kα₁)
- a powder pattern plots intensity against $2\theta$

# Planes and Miller indices @08:00
For a cubic lattice with parameter $a$:
$$d_{hkl} = \frac{a}{\sqrt{h^2 + k^2 + l^2}}$$
## Worked example: copper
FCC Cu, $a = 3.615$ Å. For (111): $d = 3.615/\sqrt{3} = 2.087$ Å, so $\sin\theta = 1.5406/(2\times2.087) = 0.369$ and $2\theta \approx 43.3°$.

# Systematic absences @18:00
The structure factor removes some reflections:
1. simple cubic: all $hkl$
2. body-centred cubic: $h + k + l$ even — (110), (200), (211)…
3. face-centred cubic: $h, k, l$ all even or all odd — (111), (200), (220), (311)…
! The pattern of absences identifies the lattice type before any refinement.

# Peak widths and refinement @28:00
- Scherrer: crystallite size $\tau = \dfrac{K\lambda}{\beta\cos\theta}$, $K \approx 0.9$, $\beta$ the FWHM in radians after removing the instrument broadening
- strain also broadens peaks (as $\tan\theta$): Williamson–Hall separates the two
- Rietveld refinement fits the whole pattern: lattice parameters, phase fractions, site occupancies
? Below what size does Scherrer stop being meaningful, and above which size can it not be used?
""",
    speech=[
        ("00:30", "Diffraction is how we know where atoms are, and it all starts with Bragg's law."),
        ("05:00", "With copper radiation the wavelength is one point five four angstrom, close to atomic spacings."),
        ("10:20", "For cubic crystals the spacing is a over the square root of h squared plus k squared plus l squared."),
        ("14:40", "For copper the one one one peak lands at about forty-three degrees two theta."),
        ("19:50", "Not every reflection appears; in FCC the indices must be all odd or all even."),
        ("25:30", "So the missing peaks tell you the lattice before you've refined anything."),
        ("30:10", "Broad peaks mean small crystallites, and Scherrer gives a size, but remove the instrument width first."),
        ("34:00", "For real quantitative work we fit the whole pattern with Rietveld refinement."),
    ]),

Example(
    "Seminar — Garnet solid electrolytes for lithium metal batteries", "Speaker: Dr P. Varga",
    "Materials building, Seminar room", "2026-10-14T16:00:00",
    summary="""Garnet Li₇La₃Zr₂O₁₂ (LLZO) is a promising solid electrolyte: stable
against lithium metal and fast-conducting in its cubic form, which needs a
dopant such as Al or Ga. Its weak point is the surface — Li₂CO₃/LiOH from air
and chemical inhomogeneity at grain boundaries raise the interface resistance
and let lithium penetrate.""",
    body=r"""
# Why solid electrolytes @02:00
- replace the flammable liquid electrolyte
- enable a lithium metal anode: much higher energy density
- requirements: ionic conductivity ≥ $10^{-4}$ S cm$^{-1}$, electronic insulation, stability against Li, good interfaces

# Garnet LLZO @08:00
$\mathrm{Li_7La_3Zr_2O_{12}}$ exists in two forms:
1. tetragonal (ordered Li): about $10^{-6}$ S cm$^{-1}$
2. cubic (disordered Li): $10^{-4}$–$10^{-3}$ S cm$^{-1}$ at room temperature
! The cubic phase is stabilised by aliovalent doping — Al³⁺ or Ga³⁺ on Li sites, or Ta⁵⁺ / Nb⁵⁺ on Zr sites; Ga-doped LLZO is among the best conductors.
- wide electrochemical window and kinetically stable against Li metal

# The interface problem @19:00
- in air, LLZO reacts with H₂O and CO₂: a LiOH / Li₂CO₃ layer forms on the surface
- this layer is a poor Li⁺ conductor and is not wetted by lithium → high interfacial resistance
- remedies: polishing, acid etching, heat treatment in inert gas, thin interlayers (e.g. Au, Al₂O₃)
- dendrites: lithium can still penetrate, often along grain boundaries; the critical current density (CCD) is the measure
## Chemical inhomogeneity
- dopants and impurities segregate to grain boundaries and the surface after processing
- surface-sensitive techniques see it: XPS (chemical state), ToF-SIMS (mapping, depth profiles), LEIS (low-energy ion scattering: the outermost atomic layer)

# Measuring it @32:00
- impedance spectroscopy: separate bulk, grain-boundary and interface arcs with an equivalent circuit
- galvanostatic cycling of Li | LLZO | Li cells at rising current to find the CCD
- stack pressure strongly changes the interface: report it
? How much of the improvement after surface treatment is chemistry, and how much is better contact?
""",
    speech=[
        ("01:00", "Thank you for having me. I'll talk about why lithium metal needs a solid electrolyte, and why garnets."),
        ("06:10", "The garnet LLZO is attractive because it does not react with lithium metal, at least not quickly."),
        ("10:40", "Undoped it's tetragonal and conducts poorly; with gallium or aluminium you get the cubic phase, a thousand times better."),
        ("16:50", "The problem is the surface. Leave it in air and you get lithium carbonate and hydroxide within minutes to hours."),
        ("21:30", "That layer doesn't conduct lithium and lithium doesn't wet it, so the interface resistance shoots up."),
        ("26:00", "We looked at what surface treatments really do with XPS, ToF-SIMS and LEIS together."),
        ("29:20", "LEIS sees only the outermost atomic layer, which is exactly where the lithium touches."),
        ("33:30", "In the impedance we can separate the bulk, the grain boundaries and the interface."),
        ("37:10", "And please always report the stack pressure, it changes the critical current density a lot."),
    ]),

Example(
    "Mechanical properties — Dislocations and strengthening", "Lecturer: Prof. J. Adeyemi",
    "Materials building, LT3", "2026-10-16T10:00:00",
    body=r"""
# Stress and strain @01:00
Engineering stress $\sigma = F/A_0$, strain $\varepsilon = \Delta L/L_0$; in the elastic range Hooke's law $\sigma = E\varepsilon$.
- yield strength: the 0.2 % offset stress
- ultimate tensile strength (UTS): the maximum of the engineering curve
- ductility: elongation at fracture
! Metals yield at stresses far below the theoretical shear strength (≈ G/10) — because of dislocations.

# Dislocations and slip @12:00
- edge dislocation: Burgers vector $\mathbf{b} \perp$ line; screw: $\mathbf{b} \parallel$ line
- slip happens on close-packed planes along close-packed directions
- FCC: $\{111\}\langle 110\rangle$, 12 slip systems — hence ductile (Cu, Al, Au)
- Schmid's law: resolved shear stress $\tau_R = \sigma\cos\phi\cos\lambda$; slip starts when $\tau_R$ reaches the critical value

# Strengthening mechanisms @25:00
Every mechanism makes dislocations harder to move:
1. grain refinement — Hall–Petch: $\sigma_y = \sigma_0 + k_y d^{-1/2}$
2. solid-solution strengthening: solute atoms strain the lattice
3. precipitation hardening: particles pinned or bypassed by Orowan bowing (Al alloys, Ni superalloys)
4. work hardening: dislocation density $\rho$ rises, $\tau \approx \alpha G b\sqrt{\rho}$ (Taylor)
! Most mechanisms trade strength for ductility; grain refinement improves both, down to the nanocrystalline range.
? Why does Hall–Petch break down for grain sizes below about 10–20 nm?
""",
    speech=[
        ("00:40", "Today, why metals are so much weaker than their bonds suggest, and how we make them stronger."),
        ("07:30", "The theoretical shear strength is around G over ten, but real metals yield a thousand times lower."),
        ("10:50", "The answer is dislocations: you move one line of atoms at a time, like a ruck in a carpet."),
        ("16:20", "FCC metals have twelve slip systems, which is why copper and aluminium are so ductile."),
        ("21:00", "Schmid's law: only the shear stress resolved on the slip plane and direction matters."),
        ("23:50", "So every strengthening mechanism is a way of getting in the way of dislocations."),
        ("28:30", "Smaller grains mean more boundaries to pile up against, that's Hall–Petch, one over root d."),
        ("33:40", "Work hardening comes from dislocations tangling with each other, stress goes as root of the density."),
    ]),
]
