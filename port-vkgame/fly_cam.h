/* MSPR_DEBUG_FLY: the debug free-fly camera (F3 in a race). Host logic only, no guest memory and no
 * window calls: the view decomposition from the game's view-projection matrix, the free-fly pose and
 * its movement, the F3 toggle and the simulation step gate. main.cpp (fly_*) does the keys, the mouse
 * and the RSX hook. Off unless MSPR_DEBUG_FLY=1. Tested by tests/test_fly_cam.c.
 *
 * View decomposition: the game's c0-c3 are a view-projection VP = P * V with V rigid and P a symmetric
 * perspective. Row 3 of VP is the view direction (the visible side has w > 0), so the look direction is
 * row3 normalised; row 1 gives the up axis; the eye is the point where clip x = y = w = 0. The fly view
 * V_fly replaces V and keeps the game's projection: VP_fly = VP * inv(V) * V_fly, so with the fly pose
 * equal to the game's pose the result is the game's VP. A matrix that does not fit the form (an
 * orthographic light matrix, a mirrored or skewed one) is not changed. */
#ifndef FLY_CAM_H
#define FLY_CAM_H

#include <math.h>
#include <string.h>

#define FLY_SPEED 6.0       /* metres per second (WASD) */
#define FLY_FAST 4.0        /* Shift */
#define FLY_SENS 0.1        /* degrees per mouse pixel */
#define FLY_PITCH_LIM 89.0  /* degrees */
#define FLY_MAX_STEP 0.1    /* seconds: a stalled frame does not jump the camera */

/* the game's camera as decomposed: eye, the visible (look) direction, the up axis, and flip = -1 when the
 * game's right axis is -(up x look) (the screen's right is then the fly camera's right: see fly_basis) */
typedef struct { double eye[3]; double look[3]; double up[3]; int flip; } fly_view;

/* the free-fly pose: position and yaw (0 = +z, +90 = +x) and pitch in degrees, flip as fly_view */
typedef struct { double eye[3]; double yaw, pitch; int flip; } fly_pose;

/* on: fly mode is active (the sim is held); init: the pose is taken from the game's view at the next draw */
typedef struct { int on; int init; } fly_mode;

/* what is held this frame: fwd, strafe (+1 right), up (+1 rises) each -1, 0 or +1; fast; mouse pixels (+x right, +y down) */
typedef struct { int fwd, strafe, up, fast; double mx, my; } fly_input;

static inline double fly_dot(const double a[3], const double b[3]) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
static inline void fly_cross(const double a[3], const double b[3], double o[3])
{
    o[0] = a[1] * b[2] - a[2] * b[1];
    o[1] = a[2] * b[0] - a[0] * b[2];
    o[2] = a[0] * b[1] - a[1] * b[0];
}
static inline int fly_unit(double v[3])
{
    const double l = sqrt(fly_dot(v, v));
    if (!(l > 1e-9)) return 0;
    v[0] /= l; v[1] /= l; v[2] /= l;
    return 1;
}

/* F3: the toggle. Turning on takes the pose from the game's view at the next draw. */
static inline void fly_toggle(fly_mode* m)
{
    m->on = !m->on;
    m->init = m->on;
}

/* The game's simulation clock: the frame step while fly mode is off, nothing while it is on. */
static inline double fly_sim_step(const fly_mode* m, double dt) { return m->on ? 0.0 : dt; }

/* visible direction and the basis of a pose: rz = flip * look, ry = world up made perpendicular to it,
 * rx = ry x rz (so that rx is the screen's right when flip is the game's). */
static inline void fly_basis(const fly_pose* p, double look[3], double rx[3], double ry[3], double rz[3])
{
    const double cp = cos(p->pitch * 3.14159265358979 / 180.0), sp = sin(p->pitch * 3.14159265358979 / 180.0);
    const double cy = cos(p->yaw * 3.14159265358979 / 180.0), sy = sin(p->yaw * 3.14159265358979 / 180.0);
    look[0] = cp * sy; look[1] = sp; look[2] = cp * cy;
    const double up[3] = { 0, 1, 0 };
    const double d = fly_dot(up, look);
    ry[0] = up[0] - d * look[0]; ry[1] = up[1] - d * look[1]; ry[2] = up[2] - d * look[2];
    if (!fly_unit(ry)) { ry[0] = 0; ry[1] = 0; ry[2] = 1; }   /* straight up or down: any level axis */
    rz[0] = p->flip * look[0]; rz[1] = p->flip * look[1]; rz[2] = p->flip * look[2];
    fly_cross(ry, rz, rx);
}

/* Move the fly camera for dt seconds of input. The mouse turns (yaw sign follows the flip so that moving
 * the mouse right always turns the view to the screen's right), the keys move along the view. */
static inline void fly_move(fly_pose* p, const fly_input* in, double dt, double speed_mul)
{
    if (!(dt > 0)) dt = 0;
    if (dt > FLY_MAX_STEP) dt = FLY_MAX_STEP;
    p->yaw += (double)p->flip * in->mx * FLY_SENS;
    p->pitch -= in->my * FLY_SENS;
    if (p->pitch > FLY_PITCH_LIM) p->pitch = FLY_PITCH_LIM;
    if (p->pitch < -FLY_PITCH_LIM) p->pitch = -FLY_PITCH_LIM;
    while (p->yaw > 180.0) p->yaw -= 360.0;
    while (p->yaw < -180.0) p->yaw += 360.0;
    double look[3], rx[3], ry[3], rz[3];
    fly_basis(p, look, rx, ry, rz);
    const double s = FLY_SPEED * (in->fast ? FLY_FAST : 1.0) * speed_mul * dt;
    const double up[3] = { 0, 1, 0 };
    for (int k = 0; k < 3; k++)
        p->eye[k] += s * ((double)in->fwd * look[k] + (double)in->strafe * rx[k] + (double)in->up * up[k]);
}

/* the fly pose at the game's view (its eye, look and flip); yaw and pitch from the look direction */
static inline void fly_pose_from_view(fly_pose* p, const fly_view* v)
{
    memcpy(p->eye, v->eye, sizeof p->eye);
    p->flip = v->flip;
    p->pitch = asin(v->look[1] < -1 ? -1 : v->look[1] > 1 ? 1 : v->look[1]) * 180.0 / 3.14159265358979;
    p->yaw = atan2(v->look[0], v->look[2]) * 180.0 / 3.14159265358979;
}

/* column-major or row-major storage of a float[16] matrix, as the scene pass reads it: the rows of the
 * camera are c0-c3 when the w row is not the unit vector, else the columns (rsx_vk_scenefx.h) */
static inline int fly_cols(const float* vp)
{
    const double nr = sqrt((double)vp[12] * vp[12] + (double)vp[13] * vp[13] + (double)vp[14] * vp[14]);
    const double nc = sqrt((double)vp[3] * vp[3] + (double)vp[7] * vp[7] + (double)vp[11] * vp[11]);
    return fabs(nc - 1.0) < fabs(nr - 1.0);
}
static inline void fly_load(const float* vp, double m[16])
{
    const int cols = fly_cols(vp);
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) m[i * 4 + j] = cols ? vp[j * 4 + i] : vp[i * 4 + j];
}
static inline void fly_store(const double m[16], const float* like, float* vp)
{
    const int cols = fly_cols(like);
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) {
            if (cols) vp[j * 4 + i] = (float)m[i * 4 + j];
            else vp[i * 4 + j] = (float)m[i * 4 + j];
        }
}

static inline void fly_mul4(const double a[16], const double b[16], double o[16])
{
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) {
            double s = 0;
            for (int k = 0; k < 4; k++) s += a[i * 4 + k] * b[k * 4 + j];
            o[i * 4 + j] = s;
        }
}

/* the view matrix (row-major, world to view) of a basis and eye: rows rx, ry, rz and -r . eye */
static inline void fly_view_matrix(const double eye[3], const double rx[3], const double ry[3], const double rz[3], double v[16])
{
    const double* r[3] = { rx, ry, rz };
    for (int i = 0; i < 3; i++) {
        v[i * 4 + 0] = r[i][0]; v[i * 4 + 1] = r[i][1]; v[i * 4 + 2] = r[i][2];
        v[i * 4 + 3] = -fly_dot(r[i], eye);
    }
    v[12] = 0; v[13] = 0; v[14] = 0; v[15] = 1;
}

/* Decompose a row-major view-projection m. Returns 1 and fills v when m is a symmetric perspective times a
 * rigid view (checked by rebuilding P = m * inv(V): its zero entries vanish and P32 is not zero). */
static inline int fly_decompose(const double m[16], fly_view* v)
{
    const double* r0 = m; const double* r1 = m + 4; const double* r3 = m + 12;
    const double up[3] = { 0, 1, 0 };
    double l[3] = { r3[0], r3[1], r3[2] };
    if (!fly_unit(l)) return 0;
    double u[3] = { r1[0], r1[1], r1[2] };
    const double d1 = fly_dot(u, l);
    u[0] -= d1 * l[0]; u[1] -= d1 * l[1]; u[2] -= d1 * l[2];
    if (!fly_unit(u)) return 0;
    if (fly_dot(u, up) < 0) { u[0] = -u[0]; u[1] = -u[1]; u[2] = -u[2]; }
    double rxa[3];
    fly_cross(u, l, rxa);                                     /* the right axis with rz = +look */
    const double p00 = fly_dot(r0, rxa);
    const int flip = p00 >= 0 ? 1 : -1;                       /* screen right = +x of the view */
    const double rz[3] = { flip * l[0], flip * l[1], flip * l[2] };
    double rx[3];
    fly_cross(u, rz, rx);
    /* the eye: clip x = y = w = 0 (rows 0, 1 and 3), by Cramer */
    const double a[3][3] = { { r0[0], r0[1], r0[2] }, { r1[0], r1[1], r1[2] }, { r3[0], r3[1], r3[2] } };
    const double det = a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
                       a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
    if (!(fabs(det) > 1e-18)) return 0;
    const double b[3] = { -r0[3], -r1[3], -r3[3] };
    double eye[3];
    for (int c = 0; c < 3; c++) {   /* Cramer: replace column c by b */
        double t[3][3];
        memcpy(t, a, sizeof t);
        for (int i = 0; i < 3; i++) t[i][c] = b[i];
        eye[c] = (t[0][0] * (t[1][1] * t[2][2] - t[1][2] * t[2][1]) - t[0][1] * (t[1][0] * t[2][2] - t[1][2] * t[2][0]) +
                  t[0][2] * (t[1][0] * t[2][1] - t[1][1] * t[2][0])) / det;
    }
    /* validate: P = m * inv(V), inv(V) = [R^T | eye] */
    double rr[3][3] = { { rx[0], rx[1], rx[2] }, { u[0], u[1], u[2] }, { rz[0], rz[1], rz[2] } };
    double inv[16];
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) inv[i * 4 + j] = rr[j][i];
        inv[i * 4 + 3] = eye[i];
    }
    inv[12] = 0; inv[13] = 0; inv[14] = 0; inv[15] = 1;
    double P[16];
    fly_mul4(m, inv, P);
    double scale = 0;
    const int nz[11][2] = { { 0, 1 }, { 0, 2 }, { 0, 3 }, { 1, 0 }, { 1, 2 }, { 1, 3 }, { 2, 0 }, { 2, 1 }, { 3, 0 }, { 3, 1 }, { 3, 3 } };
    for (int k = 0; k < 16; k++) if (fabs(P[k]) > scale) scale = fabs(P[k]);
    if (!(scale > 0) || !(fabs(P[11]) > 1e-6 * scale) || !(fabs(P[14]) > 1e-6 * scale)) return 0;   /* P32 (row 3, col 2) and P23 */
    for (int k = 0; k < 11; k++)
        if (fabs(P[nz[k][0] * 4 + nz[k][1]]) > 1e-4 * scale) return 0;
    memcpy(v->eye, eye, sizeof v->eye);
    memcpy(v->look, l, sizeof v->look);
    memcpy(v->up, u, sizeof v->up);
    v->flip = flip;
    return 1;
}

/* out = m * inv(V_game) * V_fly: the game's projection with the fly view, row-major. */
static inline void fly_retarget(const double m[16], const fly_view* g, const fly_pose* p, double out[16])
{
    double rx[3], ry[3], rz[3], look[3];
    /* the game's own basis, as fly_decompose made it */
    double rxg[3], rzg[3];
    rzg[0] = g->flip * g->look[0]; rzg[1] = g->flip * g->look[1]; rzg[2] = g->flip * g->look[2];
    fly_cross(g->up, rzg, rxg);
    double inv[16];
    for (int i = 0; i < 3; i++) {
        inv[i * 4 + 0] = rxg[i]; inv[i * 4 + 1] = g->up[i]; inv[i * 4 + 2] = rzg[i];
        inv[i * 4 + 3] = g->eye[i];
    }
    inv[12] = 0; inv[13] = 0; inv[14] = 0; inv[15] = 1;
    fly_basis(p, look, rx, ry, rz);
    double vf[16];
    fly_view_matrix(p->eye, rx, ry, rz, vf);
    double t[16];
    fly_mul4(inv, vf, t);
    fly_mul4(m, t, out);
}

/* the scene's view-projection in storage order: replaces vp when the draw is a perspective camera view */
static inline int fly_view_vp(const fly_pose* p, const float* vp_in, float* vp_out)
{
    double m[16], out[16];
    fly_load(vp_in, m);
    fly_view g;
    if (!fly_decompose(m, &g)) return 0;
    fly_retarget(m, &g, p, out);
    fly_store(out, vp_in, vp_out);
    return 1;
}

#endif
