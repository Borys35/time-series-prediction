import do_mpc
import numpy as np

def create_mpc():
    # load model matrices
    data = np.load('./notebooks/tep_mpc_model.npz')
    A = data['A']
    B = data['B']
    C = data['C']
    D = data['D']

    model_type = 'discrete'
    model = do_mpc.model.Model(model_type)

    n_states = A.shape[0]
    n_outputs = C.shape[0]

    x = model.set_variable(var_type='_x', var_name='x', shape=(n_states, 1))
    u = model.set_variable(var_type='_u', var_name='u', shape=(11, 1))

    x_next = A @ x + B @ u
    y = C @ x + D @ u

    # n_states = A.shape[0]
    # n_outputs = C.shape[0]
    # n_steps = 500

    model.set_rhs('x', x_next)
    model.set_expression('y', y)

    model.setup()

    mpc = do_mpc.controller.MPC(model)
    
    setup_mpc = {
        'n_horizon': 20,
        't_step': 1,
        'n_robust': 0,
        'store_full_solution': True,
    }
    mpc.set_param(**setup_mpc)

    Q = np.eye(41) * 1.0  
    R = np.eye(11) * 0.1

    mterm = model.aux['y'].T @ Q @ model.aux['y']
    lterm = model.aux['y'].T @ Q @ model.aux['y']

    mpc.set_objective(mterm=mterm, lterm=lterm)
    mpc.set_rterm(u=0.1)

    mpc.setup()

    estimator = do_mpc.estimator.StateFeedback(model)

    return mpc, estimator, model