import numpy as np
import argparse

def read_xyz(path):
    """Read XYZ and return atom symbols and coordinates (Nx3 array)."""
    with open(path) as f:
        lines = f.readlines()
    natoms = int(lines[0])
    elems = []
    coords = []
    for line in lines[2:2+natoms]:
        parts = line.split()
        elems.append(parts[0])
        coords.append(list(map(float, parts[1:4])))
    return elems, np.array(coords)

def write_xyz(path, elems, coords, comment):
    """Write XYZ file."""
    with open(path, 'w') as f:
        f.write(f"{len(elems)}\n{comment}\n")
        for e, (x, y, z) in zip(elems, coords):
            f.write(f"{e} {x:.6f} {y:.6f} {z:.6f}\n")

def kabsch(P, Q):
    """Compute rotation matrix R aligning P->Q (both Nx3, centered)."""
    # covariance
    C = P.T @ Q
    U, s, Vt = np.linalg.svd(C)
    d = np.sign(np.linalg.det(U @ Vt))
    R = U @ np.diag([1,1,d]) @ Vt
    return R

def rot_to_quat(R):
    """Convert rotation matrix to quaternion [w,x,y,z]."""
    t = np.trace(R)
    if t > 0:
        r = np.sqrt(1 + t)
        w = 0.5 * r
        s = 0.5 / r
        x = (R[2,1] - R[1,2]) * s
        y = (R[0,2] - R[2,0]) * s
        z = (R[1,0] - R[0,1]) * s
    else:
        # handle diagonal dominance
        i = np.argmax([R[0,0], R[1,1], R[2,2]])
        if i == 0:
            r = np.sqrt(1 + R[0,0] - R[1,1] - R[2,2])
            x = 0.5*r; s = 0.5/r
            y = (R[1,0] + R[0,1])*s
            z = (R[0,2] + R[2,0])*s
            w = (R[2,1] - R[1,2])*s
        elif i == 1:
            r = np.sqrt(1 - R[0,0] + R[1,1] - R[2,2])
            y = 0.5*r; s = 0.5/r
            x = (R[1,0] + R[0,1])*s
            z = (R[2,1] + R[1,2])*s
            w = (R[0,2] - R[2,0])*s
        else:
            r = np.sqrt(1 - R[0,0] - R[1,1] + R[2,2])
            z = 0.5*r; s = 0.5/r
            x = (R[0,2] + R[2,0])*s
            y = (R[2,1] + R[1,2])*s
            w = (R[1,0] - R[0,1])*s
    return np.array([w, x, y, z])

def quat_to_rot(q):
    """Convert quaternion [w,x,y,z] to rotation matrix."""
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1-2*(y*y+z*z),   2*(x*y - w*z), 2*(x*z + w*y)],
        [2*(x*y + w*z), 1-2*(x*x+z*z),   2*(y*z - w*x)],
        [2*(x*z - w*y),   2*(y*z + w*x), 1-2*(x*x+y*y)]
    ])

def slerp(q0, q1, t):
    """Spherical linear interpolation between quaternions."""
    dot = np.dot(q0, q1)
    if dot < 0:
        q1 = -q1
        dot = -dot
    if dot > 0.9995:
        q = q0 + t*(q1-q0)
        return q/np.linalg.norm(q)
    theta_0 = np.arccos(dot)
    q2 = q1 - dot*q0
    q2 /= np.linalg.norm(q2)
    return q0*np.cos(theta_0*t) + q2*np.sin(theta_0*t)

def main():
    parser = argparse.ArgumentParser(description="Rigid-body interpolation using molecule centroid as pivot.")
    parser.add_argument("first_xyz", help="Initial XYZ file")
    parser.add_argument("last_xyz", help="Final XYZ file")
    parser.add_argument("n_images", type=int, help="Number of images (including endpoints)")
    args = parser.parse_args()

    elems, P = read_xyz(args.first_xyz)
    _, Q = read_xyz(args.last_xyz)
    if P.shape != Q.shape:
        sys.exit("Error: Coordinates shape mismatch.")

    # centroids
    cent1 = P.mean(axis=0)
    cent2 = Q.mean(axis=0)
    # centered coords
    P0 = P - cent1
    Q0 = Q - cent2

    # rotation aligning P0->Q0
    R = kabsch(P0, Q0)
    q0 = rot_to_quat(np.eye(3))
    q1 = rot_to_quat(R)
    # translation vector
    trans = cent2 - cent1

    for i in range(args.n_images):
        u = i / (args.n_images - 1)
        qi = slerp(q0, q1, u)
        Ri = quat_to_rot(qi)
        coord_rot = (Ri @ P0.T).T  # rotate about centroid
        coord_trans = coord_rot + cent1 + u * trans  # translate
        out_file = f"{i:02d}.xyz"
        comment = f"Rigid interp step {i}/{args.n_images-1}"
        write_xyz(out_file, elems, coord_trans, comment)
        print(f"Wrote {out_file}")

if __name__ == "__main__":
    main()


