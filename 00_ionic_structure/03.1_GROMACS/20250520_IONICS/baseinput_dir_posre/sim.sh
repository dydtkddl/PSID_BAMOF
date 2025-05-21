gmx editconf -f IONIC_LIQUID0001.pdb -o IONIC_LIQUID0001.gro -box 10 10 10
gmx grompp -f em.mdp -c IONIC_LIQUID0001.gro -p topol.top -o em.tpr -v
gmx mdrun -deffnm em
gmx grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nv
gmx mdrun -deffnm nvt -nt 30
gmx grompp -f npt.mdp -c nvt.gro -r nvt.gro -t nvt.cpt -p topol.top -o npt.tpr -maxwarn 1
gmx mdrun -deffnm npt -nt 30
gmx grompp -f md.mdp -c npt.gro -r npt.gro -t npt.cpt -p topol.top -o md.tpr -maxwarn 2
gmx mdrun -deffnm md -v -nt 30
gmx traj -f md.trr -s md.tpr -oxt coords.xtc


