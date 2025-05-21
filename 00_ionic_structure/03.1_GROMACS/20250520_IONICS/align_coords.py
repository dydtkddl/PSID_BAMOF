import numpy as np
'''coords[0]은 40 x 3 리스트. 이때 0,1 ,12번 인덱스 위치를 가지고 평면벡터를 만들거야 그리고 그 평면벡터를 xy 평면으로 놓이게끔할거고
이떄 12번 원자->1번원자 벡터가 x축과평행하며 12번원자는 원점에 놓일거야
전체 시스템을 돌리고 평행이동시켜서 align시키는 코드 '''
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import plotly.graph_objects as go
import pandas as pd 
def rotation_matrix_from_vectors(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = np.dot(a, b)
    if np.isclose(c, -1.0):
        return -np.eye(3)  # 180도 회전
    if np.isclose(c, 1.0):
        return np.eye(3)  # 동일
    vx = np.array([
        [0, -v[2], v[1]],
        [v[2], 0, -v[0]],
        [-v[1], v[0], 0]
    ])
    R = np.eye(3) + vx + vx @ vx * ((1 - c) / (np.linalg.norm(v) ** 2))
    return R
def align_frame(frame_coords, plane_indices):
    """
    frame_coords : np.array, shape (N,3) - 원자 좌표 리스트
    plane_indices : list or tuple of 3 ints - 평면 정의에 사용할 원자 인덱스 3개
    
    반환:
      coords_scaled: 정렬 및 스케일링된 좌표 (np.array, shape (N,3))
      coords: 원본 좌표 (np.array, shape (N,3))
      plane_points: 평면 정의에 사용된 3개 점 좌표 리스트
      normal: 계산된 법선 벡터 (단위벡터, np.array, shape (3,))
    """
    coords = np.array(frame_coords)

    if len(plane_indices) != 3:
        raise ValueError("plane_indices는 정확히 3개의 인덱스를 가져야 합니다.")
    
    pA, pB, pC = coords[plane_indices[0]], coords[plane_indices[1]], coords[plane_indices[2]]

    # 평면 법선벡터: (pA-pC) x (pB-pC)
    v1 = pA - pC
    v2 = pB - pC
    normal = np.cross(v1, v2)
    normal /= np.linalg.norm(normal)

    # 1단계 회전: 평면 법선벡터 → z축
    R1 = rotation_matrix_from_vectors(normal, np.array([0, 0, 1]))
    coords_rot1 = coords @ R1.T

    # 2단계 회전: xy평면에 투영된 (pA - pC) 벡터 → x축
    new_pA = coords_rot1[plane_indices[0]]
    new_pC = coords_rot1[plane_indices[2]]
    vec = new_pA - new_pC
    vec_xy = np.array([vec[0], vec[1], 0.0])
    if np.linalg.norm(vec_xy) < 1e-8:
        raise ValueError("두 점을 잇는 벡터의 xy 성분이 거의 0입니다. 회전 정의 불가능.")
    vec_xy /= np.linalg.norm(vec_xy)
    R2 = rotation_matrix_from_vectors(vec_xy, np.array([1, 0, 0]))
    coords_rot2 = coords_rot1 @ R2.T

    # 평행이동: pC를 원점으로
    coords_aligned = coords_rot2 - coords_rot2[plane_indices[2]]

    # 리스케일: 원본 기준 거리 유지
    d_original = np.linalg.norm(pA - pC)
    d_aligned = np.linalg.norm(coords_aligned[plane_indices[0]] - coords_aligned[plane_indices[2]])
    scale_factor = d_original / d_aligned
    coords_scaled = coords_aligned * scale_factor

    plane_points = [pA, pB, pC]

    return coords_scaled, coords, plane_points, normal

def plot_before_after_mpl(original, aligned, triangle_pts, normal_vec):
    fig = plt.figure(figsize=(14, 6))
    tri = np.array(triangle_pts)
    center = np.mean(tri, axis=0)
    axis_len = 1.5

    # ▶️ 원본 좌표계
    ax1 = fig.add_subplot(121, projection='3d')
    ax1.set_title("Before Alignment")
    original = np.array(original)

    # 음이온 (0~14), 양이온 (15~)
    ax1.scatter(*original[:15].T, color='#1f77b4', s=20, label='Anion')
    ax1.scatter(*original[15:].T, color='#ff7f0e', s=20, label='Cation')

    # 삼각형 평면 영역 색칠
    ax1.plot_trisurf(tri[:, 0], tri[:, 1], tri[:, 2], color='cyan', alpha=0.4)

    # 법선 벡터 (빨간색)
    ax1.quiver(*center, *normal_vec, length=1.0, color='red', linewidth=2)

    ax1.legend()

    # ▶️ 정렬된 좌표계
    ax2 = fig.add_subplot(122, projection='3d')
    ax2.set_title("After Alignment")
    aligned = np.array(aligned)

    # 음이온 / 양이온 구분 시각화
    ax2.scatter(*aligned[:15].T, color='#1f77b4', s=20, label='Anion')
    ax2.scatter(*aligned[15:].T, color='#ff7f0e', s=20, label='Cation')

    # 정렬된 평면 및 법선벡터 다시 계산
    tri_aligned = aligned[[0, 1, 12]]
    center_aligned = np.mean(tri_aligned, axis=0)
    v1 = tri_aligned[0] - tri_aligned[2]
    v2 = tri_aligned[1] - tri_aligned[2]
    normal_aligned = np.cross(v1, v2)
    normal_aligned /= np.linalg.norm(normal_aligned)

    # 삼각형 평면 영역 색칠
    ax2.plot_trisurf(tri_aligned[:, 0], tri_aligned[:, 1], tri_aligned[:, 2], color='cyan', alpha=0.4)

    # xyz 축 (검정)
    ax2.plot([0, axis_len], [0, 0], [0, 0], 'k')  # x
    ax2.plot([0, 0], [0, axis_len], [0, 0], 'k')  # y
    ax2.plot([0, 0], [0, 0], [0, axis_len], 'k')  # z

    # 법선 벡터 (빨간색)
    ax2.quiver(*center_aligned, *normal_aligned, length=1.0, color='red', linewidth=2)

    ax2.legend()
    plt.tight_layout()
    plt.show()
def plot_before_after_plotly(original, aligned, triangle_pts, normal_vec,plane_indices, html=False, show=False):
    original = np.array(original)
    aligned = np.array(aligned)
    tri = np.array(triangle_pts)
    center = np.mean(tri, axis=0)

    def mesh_triangle(tri_coords):
        return go.Mesh3d(
            x=tri_coords[:, 0], y=tri_coords[:, 1], z=tri_coords[:, 2],
            color='cyan', opacity=0.4,
            i=[0], j=[1], k=[2],
            name='Plane'
        )

    def normal_arrow_line(center, vector, length=1.0, opacity=0.5):
        vec_norm = vector / np.linalg.norm(vector)
        end = center + vec_norm * length
        return go.Scatter3d(
            x=[center[0], end[0]],
            y=[center[1], end[1]],
            z=[center[2], end[2]],
            mode='lines',
            line=dict(color='red', width=6),
            opacity=opacity,
            name='Normal Vector'
        )

    def axis_lines():
        axis_len = 1.5
        return [
            go.Scatter3d(x=[0, axis_len], y=[0, 0], z=[0, 0], mode='lines', line=dict(color='black'), showlegend=False),
            go.Scatter3d(x=[0, 0], y=[0, axis_len], z=[0, 0], mode='lines', line=dict(color='black'), showlegend=False),
            go.Scatter3d(x=[0, 0], y=[0, 0], z=[0, axis_len], mode='lines', line=dict(color='black'), showlegend=False)
        ]

    # Before traces
    trace_before_anion = go.Scatter3d(
        x=original[:15, 0], y=original[:15, 1], z=original[:15, 2],
        mode='markers',
        marker=dict(color='#1f77b4', size=4),
        name='Anion (Before)'
    )
    trace_before_cation = go.Scatter3d(
        x=original[15:, 0], y=original[15:, 1], z=original[15:, 2],
        mode='markers',
        marker=dict(color='#ff7f0e', size=4),
        name='Cation (Before)'
    )
    trace_before_plane = mesh_triangle(tri)
    trace_before_normal = normal_arrow_line(center, normal_vec, length=1.0, opacity=0.8)

    # After traces
    tri_aligned = aligned[plane_indices]
    center_aligned = np.mean(tri_aligned, axis=0)
    v1 = tri_aligned[0] - tri_aligned[2]
    v2 = tri_aligned[1] - tri_aligned[2]
    normal_aligned = np.cross(v1, v2)
    normal_aligned /= np.linalg.norm(normal_aligned)

    trace_after_anion = go.Scatter3d(
        x=aligned[:15, 0], y=aligned[:15, 1], z=aligned[:15, 2],
        mode='markers',
        marker=dict(color='#1f77b4', size=4),
        name='Anion (After)'
    )
    trace_after_cation = go.Scatter3d(
        x=aligned[15:, 0], y=aligned[15:, 1], z=aligned[15:, 2],
        mode='markers',
        marker=dict(color='#ff7f0e', size=4),
        name='Cation (After)'
    )
    trace_after_plane = mesh_triangle(tri_aligned)
    trace_after_normal = normal_arrow_line(center_aligned, normal_aligned, length=1.0, opacity=0.8)
    trace_after_axes = axis_lines()

    fig = go.Figure()

    # 왼쪽 (Before)
    for trace in [trace_before_anion, trace_before_cation, trace_before_plane, trace_before_normal]:
        trace.update(scene='scene')
        fig.add_trace(trace)

    # 오른쪽 (After)
    for trace in [trace_after_anion, trace_after_cation, trace_after_plane, trace_after_normal] + trace_after_axes:
        trace.update(scene='scene2')
        fig.add_trace(trace)

    fig.update_layout(
        scene=dict(
            domain=dict(x=[0, 0.48]),
            xaxis_title='X', yaxis_title='Y', zaxis_title='Z',
            aspectmode='data',
        ),
        scene2=dict(
            domain=dict(x=[0.52, 1.0]),
            xaxis_title='X', yaxis_title='Y', zaxis_title='Z',
            aspectmode='data',
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=600,
        title="Before vs After Alignment (Interactive)"
    )

    if html:
        fig.write_html("alignment_comparison.html")
    if show:
        fig.show()


with open("./coords_xtc_dump.txt" , "r") as f:
    data = f.readlines()
strt_idxs = [ i for i, d in enumerate(data)  if "coords.xtc" in d] 
trjs = []
for i, strt in enumerate(strt_idxs):
    try: 
        trjs.append(data[strt_idxs[i] : strt_idxs[i+1]])
    except: 
        trjs.append(data[strt_idxs[i] : ])
boxes = []
coords = []
for trj in trjs:
    box = trj[3:6]
    coord = trj[7:]
    newcoord = []   
    for i in coord:
        xyz = [ float(x.strip()) for x in i.split("{")[1].split("}")[0].split(",")]
        newcoord.append(xyz)
    coords.append(newcoord)

    newbox = []
    for i in box: 
        boxvec = [ float(x.strip()) for x in i.split("{")[1].split("}")[0].split(",")]
        newbox.append(boxvec)
    boxes.append(newbox)
import numpy as np

# 예: newcoord가 리스트나 numpy 배열이라 가정
point_12 = np.array(newcoord[12])
point_16 = np.array(newcoord[16])

distance = np.linalg.norm(point_12 - point_16)
print(distance)
if distance <= 1:
    # 예시 좌표 데이터로 실행
    aligned, original, triangle_pts, normal_vec = align_frame(coords[-1],[15,20,21])
    # 시각화 실행
    # plot_before_after_mpl(original, aligned, triangle_pts, normal_vec)
    plot_before_after_plotly(original, aligned, triangle_pts, normal_vec,[15,20,21], True, False)

    aligns = []
    atoms = ["S","S","F","F","F","F","F","F","O","O","O","O","N","C","C","N","N","C","C","C","C","C","C","C","C","H","H","H","H","H","H","H","H","H","H","H","H","H","H","H" ]
    xyzfiles = []
    for c in coords: 
        xyzfile = f'''{len(atoms)}\n\n'''
        aligned, original, triangle_pts, normal_vec = align_frame(c,[15,20,21])
        aligns.append(aligned)
        flip = ( list(aligned)[12][2] < 0  )
        for atom, line in zip ( atoms, aligned): 
            xxx = [x*10 for x in line]
            if flip:
                xxx[2] = -xxx[2]
            xyz_ = ' '.join([f"{x:.6f}" for x in xxx])
            # xyz_ = ' '.join([f"{x*10:.6f}" for x in line])
            xyzfile+=f"{atom} {xyz_}\n"
        xyzfiles.append(xyzfile)
    # print(xyzfile)
    integrated_xyz = ''.join(xyzfiles)
    with open( "integrated_xyz.xyz" , 'w') as f:
        f.write(integrated_xyz)
    with open( "final_coord4.xyz" , 'w') as f:
        f.write(xyzfile)