/* fly_cam.h: the view decomposition of a game-style view-projection (left- and right-handed), the retarget
 * to a fly view (identity at the game's pose, the screen's right stays the right), the movement vector from
 * key states, the mouse turn, the F3 toggle and the simulation gate. */
#include "fly_cam.h"
#include <assert.h>
#include <stdio.h>

#define PI 3.14159265358979
static int near(double a, double b, double tol) { return fabs(a - b) <= tol; }

/* a symmetric perspective, left-handed (w = +z) or right-handed (w = -z, GL style) */
static void persp(int rh, double m[16])
{
    memset(m, 0, 16 * sizeof(double));
    const double f = 1.7, n = 0.5, F = 900.0;
    if (!rh) {
        const double q = F / (F - n);
        m[0] = f; m[5] = f * 1.3; m[10] = q; m[11] = -q * n; m[14] = 1;
    } else {
        m[0] = f; m[5] = f * 1.3; m[10] = (F + n) / (n - F); m[11] = 2 * F * n / (n - F); m[14] = -1;
    }
}

/* a rigid view for an eye, look (visible) direction and up, right-handed basis rx = up x rz with rz = flip*look */
static void view_of(const double eye[3], const double look[3], int flip, double v[16])
{
    fly_pose p;
    memcpy(p.eye, eye, sizeof p.eye);
    p.flip = flip;
    p.yaw = atan2(look[0], look[2]) * 180.0 / PI;
    p.pitch = asin(look[1]) * 180.0 / PI;
    double lk[3], rx[3], ry[3], rz[3];
    fly_basis(&p, lk, rx, ry, rz);
    fly_view_matrix(eye, rx, ry, rz, v);
}

static void mul_pv(const double P[16], const double V[16], double VP[16]) { fly_mul4(P, V, VP); }

static void ndc(const double VP[16], const double x[3], double out[2])
{
    double c[4];
    for (int i = 0; i < 4; i++) c[i] = VP[i * 4] * x[0] + VP[i * 4 + 1] * x[1] + VP[i * 4 + 2] * x[2] + VP[i * 4 + 3];
    out[0] = c[0] / c[3]; out[1] = c[1] / c[3];
}

static void check_retarget_identity(int rh, int flip_expected)
{
    const double eye[3] = { 10, 2, -5 };
    const double s = sin(30 * PI / 180), c = cos(30 * PI / 180), t = sin(-10 * PI / 180), cc = cos(-10 * PI / 180);
    const double look[3] = { cc * s, t, cc * c };
    double P[16], V[16], VP[16];
    persp(rh, P);
    view_of(eye, look, flip_expected, V);
    mul_pv(P, V, VP);

    fly_view g;
    assert(fly_decompose(VP, &g));
    assert(near(g.eye[0], eye[0], 1e-6) && near(g.eye[1], eye[1], 1e-6) && near(g.eye[2], eye[2], 1e-6));
    assert(near(g.look[0], look[0], 1e-9) && near(g.look[1], look[1], 1e-9) && near(g.look[2], look[2], 1e-9));
    assert(g.flip == flip_expected);

    /* the fly pose equal to the game's: the retarget is the game's VP */
    fly_pose p;
    fly_pose_from_view(&p, &g);
    double out[16];
    fly_retarget(VP, &g, &p, out);
    for (int k = 0; k < 16; k++) assert(near(out[k], VP[k], 1e-6 * (fabs(VP[k]) + 1)));

    /* screen right = +x of the view: a point to the screen's right has a positive NDC x in the game's VP */
    double right[3];
    fly_cross(g.up, look, right);            /* the game's up x look: the screen's right iff flip = -1 ... checked below */
    double rxg[3] = { g.flip * right[0], g.flip * right[1], g.flip * right[2] };
    const double X[3] = { eye[0] + 20 * look[0] + 3 * rxg[0], eye[1] + 20 * look[1] + 3 * rxg[1], eye[2] + 20 * look[2] + 3 * rxg[2] };
    double n[2];
    ndc(VP, X, n);
    assert(n[0] > 0 && near(n[1], 0.0, 1.0));   /* 3 units to the right of the look line: right of the centre */
}

static void test_decompose(void)
{
    check_retarget_identity(0, 1);   /* left-handed: the view's z is the look direction */
    check_retarget_identity(1, -1);  /* right-handed (camera looks down -z): flip -1 */
}

static void test_reject(void)
{
    double P[16] = { 0 }, V[16], VP[16];
    /* orthographic (w = 1): an ortho light matrix is not the camera */
    P[0] = 0.01; P[5] = 0.02; P[10] = 0.001; P[11] = 0.5; P[15] = 1;
    const double eye[3] = { 0, 0, 0 }, look[3] = { 0, 0, 1 };
    view_of(eye, look, 1, V);
    mul_pv(P, V, VP);
    fly_view g;
    assert(!fly_decompose(VP, &g));
    /* a skewed (off-centre) perspective is not changed either */
    persp(0, P);
    P[2] = 0.3;
    mul_pv(P, V, VP);
    assert(!fly_decompose(VP, &g));
    /* a degenerate matrix */
    memset(VP, 0, sizeof VP);
    assert(!fly_decompose(VP, &g));
}

static void test_move(void)
{
    fly_pose p = { { 1, 2, 3 }, 0, 0, 1 };
    fly_input in;
    memset(&in, 0, sizeof in);
    in.fwd = 1;
    fly_move(&p, &in, 1.0 / 60.0, 1.0);
    assert(near(p.eye[0], 1, 1e-12) && near(p.eye[1], 2, 1e-12) && near(p.eye[2], 3 + FLY_SPEED / 60.0, 1e-9));

    /* strafe right along the screen's right (+x at yaw 0, flip +1), Shift fast */
    fly_pose q = { { 0, 0, 0 }, 0, 0, 1 };
    memset(&in, 0, sizeof in);
    in.strafe = 1; in.fast = 1;
    fly_move(&q, &in, 0.1, 1.0);
    assert(near(q.eye[0], FLY_SPEED * FLY_FAST * 0.1, 1e-9) && near(q.eye[2], 0, 1e-12));

    /* the view's forward follows pitch: looking up, forward gains height */
    fly_pose r = { { 0, 0, 0 }, 0, 45, 1 };
    memset(&in, 0, sizeof in);
    in.fwd = 1;
    fly_move(&r, &in, 0.1, 1.0);
    assert(r.eye[1] > 0 && near(r.eye[1], FLY_SPEED * 0.1 * sin(45 * PI / 180), 1e-9));

    /* up is straight along world y; a stalled frame moves at most FLY_MAX_STEP */
    fly_pose u = { { 0, 0, 0 }, 0, 0, 1 };
    memset(&in, 0, sizeof in);
    in.up = -1;
    fly_move(&u, &in, 5.0, 1.0);
    assert(near(u.eye[1], -FLY_SPEED * FLY_MAX_STEP, 1e-9));

    /* no keys, no mouse: no change */
    fly_pose z = { { 4, 5, 6 }, 10, 10, 1 };
    memset(&in, 0, sizeof in);
    fly_move(&z, &in, 0.2, 1.0);
    assert(near(z.eye[0], 4, 0) && near(z.eye[2], 6, 0) && near(z.yaw, 10, 0) && near(z.pitch, 10, 0));
}

static void test_mouse(void)
{
    fly_input in;
    memset(&in, 0, sizeof in);
    fly_pose p = { { 0, 0, 0 }, 0, 0, 1 };
    in.mx = 100;
    fly_move(&p, &in, 0.0, 1.0);
    assert(near(p.yaw, 100 * FLY_SENS, 1e-12));
    /* the mouse right turns to the screen's right for either handedness */
    fly_pose f = { { 0, 0, 0 }, 0, 0, -1 };
    fly_move(&f, &in, 0.0, 1.0);
    assert(near(f.yaw, -100 * FLY_SENS, 1e-12));
    /* down on the screen (+y) looks down; the pitch stops at the limit */
    fly_pose d = { { 0, 0, 0 }, 0, 0, 1 };
    memset(&in, 0, sizeof in);
    in.my = -5000;
    fly_move(&d, &in, 0.0, 1.0);
    assert(near(d.pitch, FLY_PITCH_LIM, 1e-12));
    in.my = 20000;
    fly_move(&d, &in, 0.0, 1.0);
    assert(near(d.pitch, -FLY_PITCH_LIM, 1e-12));
}

static void test_pause(void)
{
    fly_mode m = { 0, 0 };
    double clock = 0;
    for (int i = 0; i < 60; i++) clock += fly_sim_step(&m, 1.0 / 30.0);    /* the game runs */
    assert(near(clock, 2.0, 1e-9));

    fly_toggle(&m);                                                           /* F3 on */
    assert(m.on && m.init);
    for (int i = 0; i < 1000; i++) clock += fly_sim_step(&m, 1.0 / 30.0);   /* held: the clock does not move */
    assert(near(clock, 2.0, 1e-9));

    fly_toggle(&m);                                                           /* F3 off: resumes where it stopped */
    assert(!m.on);
    for (int i = 0; i < 30; i++) clock += fly_sim_step(&m, 1.0 / 30.0);
    assert(near(clock, 3.0, 1e-9));
    fly_toggle(&m);
    fly_toggle(&m);
    assert(!m.on);            /* on, then off again */
    fly_toggle(&m);
    assert(m.on && m.init);   /* on once more: the pose is taken from the game's view again */
}

static void test_retarget_moves(void)
{
    /* with the pose moved 6 m forward along the look, the point on the look line stays in the centre (its
     * depth changes, not its screen position), and the projection is still the game's */
    const double eye[3] = { 0, 0, 0 }, look[3] = { 0, 0, 1 };
    double P[16], V[16], VP[16];
    persp(0, P);
    view_of(eye, look, 1, V);
    mul_pv(P, V, VP);
    fly_view g;
    assert(fly_decompose(VP, &g));
    fly_pose p;
    fly_pose_from_view(&p, &g);
    fly_input in;
    memset(&in, 0, sizeof in);
    in.fwd = 1;
    fly_move(&p, &in, 1.0, 1.0);
    double out[16];
    fly_retarget(VP, &g, &p, out);
    const double X[3] = { 0, 0, 20 };
    double n[2];
    ndc(out, X, n);
    assert(near(n[0], 0, 1e-9) && near(n[1], 0, 1e-9));
    /* a point 2 units to the side of the look line keeps its screen x as the pose moves along the line */
    const double Y[3] = { 2, 0, 20 };
    double a[2], b[2];
    ndc(VP, Y, a);
    ndc(out, Y, b);
    /* the step is clamped to FLY_MAX_STEP (0.1 s): 0.6 m forward, so the point 20 m ahead is 19.4 m ahead
     * and its NDC x grows by 20 / 19.4 */
    assert(near(a[0], 1.7 * 2 / 20.0, 1e-9));
    assert(near(p.eye[2], FLY_SPEED * FLY_MAX_STEP, 1e-9));
    assert(near(b[0], a[0] * 20.0 / (20.0 - FLY_SPEED * FLY_MAX_STEP), 1e-6));
}

static void test_vp_store(void)
{
    /* a float VP in storage order: the same result whichever way the matrix is stored */
    double P[16], V[16], VP[16];
    persp(0, P);
    const double eye[3] = { 3, 1, -2 }, look[3] = { 0, 0, 1 };
    view_of(eye, look, 1, V);
    mul_pv(P, V, VP);
    float rowv[16], colv[16], out_r[16], out_c[16];
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) { rowv[i * 4 + j] = (float)VP[i * 4 + j]; colv[j * 4 + i] = (float)VP[i * 4 + j]; }
    fly_pose p = { { 3, 1, -2 }, 0, 0, 1 };
    p.eye[2] = -2 + 4;   /* 4 m further */
    assert(fly_view_vp(&p, rowv, out_r));
    assert(fly_view_vp(&p, colv, out_c));
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 4; j++) {
            assert(near(out_r[i * 4 + j], out_c[j * 4 + i], 1e-4 * (fabs(out_r[i * 4 + j]) + 1)));
        }
    /* at the game's pose the stored result is the stored input */
    fly_pose same = { { 3, 1, -2 }, 0, 0, 1 };
    assert(fly_view_vp(&same, rowv, out_r));
    for (int k = 0; k < 16; k++) assert(near(out_r[k], rowv[k], 1e-4 * (fabs(rowv[k]) + 1)));
}

int main(void)
{
    test_decompose();
    test_reject();
    test_move();
    test_mouse();
    test_pause();
    test_retarget_moves();
    test_vp_store();
    printf("test_fly_cam: all checks passed\n");
    return 0;
}
