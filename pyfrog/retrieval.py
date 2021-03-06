import numpy as np
from scipy.interpolate import interp2d
import time
import warnings
import pyfrog.frog
from pyfrog import errors

def vanilla( trace, g_limit=1e-5,
                    max_iter=500,
                    max_time=10,
                    stagnation_count = 100,
                    show_every=None,
                    spectrum=None, phase=None,
                    spectrum_gate=None, phase_gate=None,
                    nonlinearity = 'shg' ):
    """
        vanilla( trace, **kwargs ) retrieves the pulse that generated the given frog trace using the 'vanilla' algorithm. The unknown pulse and the gate are generated from spectrum+phase and spectrum_gate+phase_gate, respectively. If spectrum or phase is None, the algorithm uses random numbers as starting points. If spectrum_gate or phase_gate is None, the gate pulse is equal to the unknown pulse.

        arguments:
            trace : FROG trace.
            g_limit : default 1e-5, retrieval is stopped if the error is smaller than g_limit.
            max_iter : default 1e3, maximum number of iterations allowed.
            max_time : default 10, time in seconds allowed.
            stagnation_count : default 100, allow the algorithm to continue for 'stagnation_count' iterations without improvement before it is stopped.
            show_every : default 1e30, shows the FROG error every 'show_every' iterations.
            spectrum : vector containing the power spectral density (PSD) of the pulse.
            phase : vector containing the spectral phase of the pulse.
            spectrum_gate (optional) : vector containing the PSD of the gate pulse.
            phase_gate (optional) : vector containing the spectral phase of the gate pulse.
            nonlinearity : name of the nonlinearity. Default is 'shg'. Other nonlinearities are currently not available

        returns:
            E : complex electric field of the pulse in spectral domain.
                retrieved spectrum is therefore abs(E)**2
                retrieved phase is np.angle(E)
    """
    Nf = trace.shape[1]
    if show_every is None:
        show_every = 1e30
    if spectrum is None:
        spectrum = np.random.rand( Nf )
    if phase is None:
        phase = np.random.rand( Nf ) * 2 * np.pi

    P_f = np.sqrt( abs(spectrum) ) * np.exp( -1j * phase )
    #TODO why is the frequency axis reversed
    P_f = np.flip( P_f )
    P_t = np.fft.ifft( P_f )

    if (spectrum_gate is None) or (phase_gate is None):
        G_f = P_f.copy()
        G_t = P_t.copy()
    else:
        G_f = np.sqrt( spectrum_gate ) * np.exp( -1j * phase_gate )
        G_t = np.fft.ifft( G_f )

    if nonlinearity == 'shg':
        _gamma = lambda x: x
        _invgamma = lambda x: x
    converged = False
    E_best = P_t.copy()
    gbest = 1e30
    G = 1e30
    not_improved = 0
    iterations = 0
    if not 'errors' in globals():
        global errors
        errors = []
    start = time.time()
    while iterations < max_iter and \
            (time.time()-start) < max_time and \
            G > g_limit and \
            not_improved < stagnation_count:
        iterations += 1
        sim_trace, O_f = pyfrog.frog._generate_trace( P_t, P_t, return_field=True )
        G = pyfrog.frog.g_error( trace, sim_trace )
        errors.append( G )
        if iterations%show_every == 0:
            print( "Vanilla algorithm, error={:.3e}, time elapsed={:.2f}s".format(gbest, time.time()-start) )

        if gbest < G:
            not_improved += 1
        else:
            not_improved = 0
            gbest = G
            E_best = P_t.copy()

        # mute the warning created by devision of abs(O_f)
        old_err_settings = np.seterr( invalid='ignore' )
        O_f = O_f/abs(O_f) * np.sqrt( trace )
        np.seterr( invalid=old_err_settings['invalid'] )

        O_f[ np.isnan(O_f) ] = 0
        O_t = np.fft.ifft( O_f, axis=0   )
        P_t = np.sum( O_t, axis=1 )
        P_t = P_t / np.amax( abs(P_t) )

    E_best = np.roll( E_best, -np.argmax( abs(E_best)**2 ) )
    E = np.fft.ifft( E_best )
    E /= np.amax( abs( E ) )
    #TODO why is the frequency axis reversed
    return np.flip( E )


def pcgpa( trace, method='svd', g_limit=1e-10,
                   max_iter=500,
                   max_time=10,
                   stagnation_count = 100,
                   show_every=None,
                   spectrum=None, phase=None,
                   spectrum_gate=None, phase_gate=None,
                   nonlinearity = 'shg' ):
    """
        pcgpa( trace, **kwargs ) retrieves the pulse that generated the given frog trace using the principle component generalized projection algorithm. The unknown pulse and the gate are generated from spectrum+phase and spectrum_gate+phase_gate, respectively. If spectrum or phase is None, the algorithm uses random numbers as starting points. If spectrum_gate or phase_gate is None, the gate pulse is equal to the unknown pulse.

        arguments:
            trace : FROG trace.
            method : principle component method, either 'svd' (singular value decomposition), 'power2' (power method p=2) or 'power' (power method p=1).
            g_limit : default 1e-5, retrieval is stopped if the error is smaller than g_limit.
            max_iter : default 1e3, maximum number of iterations allowed.
            max_time : default 10, time in seconds allowed.
            stagnation_count : default 100, allow the algorithm to continue for 'stagnation_count' iterations without improvement before it is stopped.
            show_every : default 1e30, shows the FROG error every 'show_every' iterations.
            spectrum : vector containing the power spectral density (PSD) of the pulse.
            phase : vector containing the spectral phase of the pulse.
            spectrum_gate (optional) : vector containing the PSD of the gate pulse.
            phase_gate (optional) : vector containing the spectral phase of the gate pulse.
            nonlinearity : name of the nonlinearity. Default is 'shg'. Other nonlinearities are currently not available

        returns:
            E : complex electric field of the pulse in spectral domain.
                retrieved spectrum is therefore abs(E)**2
                retrieved phase is np.angle(E)
    """
    Nf = trace.shape[1] 
    if show_every is None:
        show_every = 1e30
    if spectrum is None:
        spectrum = np.random.rand( Nf )
    if phase is None:
        phase = np.random.rand( Nf ) * 2 * np.pi
    P_f = np.sqrt( abs(spectrum) ) * np.exp( -1j * phase )
    P_t = np.fft.ifft( P_f )

    if (spectrum_gate is None) or (phase_gate is None):
        G_f = P_f.copy()
        G_t = P_t.copy()
    else:
        G_f = np.sqrt( spectrum_gate ) * np.exp( -1j * phase_gate )
        G_t = np.fft.ifft( G_f )

    if nonlinearity == 'shg':
        _gamma = lambda x: x
        _invgamma = lambda x: x
    E_best = P_t.copy()
    converged = False
    G = 1e30
    gbest = 1e30
    not_improved = 0
    iterations = 0
    start = time.time()
    if not 'errors' in globals():
        global errors
        errors = []
    while iterations < max_iter and \
            (time.time()-start) < max_time and \
            G > g_limit and \
            not_improved < stagnation_count:
        iterations += 1
        sim_trace, O_f = pyfrog.frog._generate_trace( P_t, P_t, return_field=True )
        G = pyfrog.frog.g_error( trace, sim_trace )
        errors.append( G )
        if iterations%show_every == 0:
            print( "PCGPA, error={:.3e}, time elapsed={:.2f}s".format(gbest, time.time()-start) )
        if gbest < G:
            not_improved += 1
        else:
            not_improved = 0
            gbest = G
            E_best = P_t.copy()

        # mute the warning created by devision of abs(O_f)
        old_err_settings = np.seterr( invalid='ignore' )
        O_f = O_f/abs(O_f) * np.sqrt( trace )
        np.seterr( invalid=old_err_settings['invalid'] )
        old_err_settings = np.seterr( divide='ignore' )

        O_f[ np.isnan(O_f) ] = 0
        O_t = np.fft.ifft( O_f, axis=0   )
        O_t = pyfrog.frog.tau_to_OPF( O_t )
        
        if method == 'svd':
            u, w, vt = np.linalg.svd( O_t )
            ind = np.argmax( abs(w) )
            P_t = u[:,ind]
            G_t = vt[ind,:]
        elif method == 'power2':
            P_t = np.dot( np.matmul(O_t, np.matmul( np.transpose(O_t),np.matmul(O_t, np.transpose(O_t)))), P_t )
            G_t = np.dot( np.matmul(np.transpose(O_t), np.matmul( O_t, np.matmul(np.transpose(O_t), O_t) ) ), G_t )
        elif method == 'power':
            P_t = np.dot( np.matmul(O_t, np.transpose(O_t)), P_t )
            G_t = np.dot( np.matmul(np.transpose(O_t), O_t), G_t )

        P_t = P_t / np.amax(abs(P_t))
        G_t = G_t / np.amax(abs(G_t))

    E_t = pyfrog.grid.remove_group_delay( E_best )
    E = np.fft.ifft( E_t )
    E /= np.amax( abs( E ) )
    #TODO why is the frequency axis reversed
    return np.flip( E )


def rana_spectrum( trace, padding=None, threshold=1e-3 ):
    """
    rana_spectrum( trace, padding=None, threshold=1e-3 ) retrieves the fundamental spectrum from a frog trace by applying the Paley-Wiener theorem. The whole procedure is described in R. Jafari, T. Jones, and R. Trebino, "100% reliable algorithm for second-harmonic-generation frequency-resolved optical gating," Opt. Express  27, 2112-2124 (2019). 

    arguments:
        trace : the input FROG trace
        padding (optional) : number of zeros used for zero padding to increase the resolution in the time domain. The default will use 2 * M zeros at both sides.
        threshold (optional) : threshold for checking the continuity of the derivatives of the Fourier-transform of the spectrum.

    returns:
        spectrum : vector containing the power spectral density 
    """
    Nf = trace.shape[1] 
    if padding is None:
        padding = 2 * Nf
    freq_marginal = np.fft.fftshift( np.sum( trace, 1 ) )
    freq_marginal = np.concatenate( (np.zeros(padding), freq_marginal, np.zeros(padding) ) )
    freq_marginal = np.fft.fftshift( freq_marginal )
    s_t = np.sqrt( np.fft.ifft( freq_marginal ) )
    s_t /= np.amax( abs( s_t ) )
    to_roll = int( Nf/2 - np.argmax(abs(s_t)))
    s_t = np.roll( s_t, to_roll )
    s_t_p = s_t
    s_t_n = - s_t
    t_i = np.argmax( abs(s_t_p) )
    positive = True
    s_t[ t_i ] = s_t_p[ t_i ]
    alpha = 0.09
    beta = 0.425
    gamma = 1
    threshold = 1e-3
    for i in range( t_i+1, Nf ):
        if positive:
            if abs( s_t[i-1] ) + abs( s_t_p[i] ) < threshold :
                delta_0_p = s_t_p[i] - s_t[i-1]
                delta_0_n = s_t_n[i] - s_t[i-1]
                delta_1_p = s_t_p[i] - 2 * s_t[i-1] + s_t[i-2]
                delta_1_n = s_t_n[i] - 2 * s_t[i-1] + s_t[i-2]
                delta_2_p = s_t_p[i] - 3 * s_t[i-1] + 3 * s_t[i-2] - s_t[i-3]
                delta_2_n = s_t_p[i] - 3 * s_t[i-1] + 3 * s_t[i-2] - s_t[i-3]

                epsilon_p = alpha * abs(delta_0_p)**2 + beta * abs(delta_1_p)**2 + gamma * abs(delta_2_p)**2
                epsilon_n = alpha * abs(delta_0_n)**2 + beta * abs(delta_1_n)**2 + gamma * abs(delta_2_n)**2
            else:
                if abs( s_t[i-1] - s_t_p[i] ) < abs( s_t[i-1] - s_t_n[i] ):
                    s_t[i] = s_t_p[i]
                else:
                    positive=False
                    s_t[i] = s_t_n[i]
        else: 
            if abs( s_t[i-1] ) + abs( s_t_n[i] ) < threshold :
                delta_0_p = s_t_p[i] - s_t[i-1]
                delta_0_n = s_t_n[i] - s_t[i-1]
                delta_1_p = s_t_p[i] - 2 * s_t[i-1] + s_t[i-2]
                delta_1_n = s_t_n[i] - 2 * s_t[i-1] + s_t[i-2]
                delta_2_p = s_t_p[i] - 3 * s_t[i-1] + 3 * s_t[i-2] - s_t[i-3]
                delta_2_n = s_t_p[i] - 3 * s_t[i-1] + 3 * s_t[i-2] - s_t[i-3]

                epsilon_p = alpha * abs(delta_0_p)**2 + beta * abs(delta_1_p)**2 + gamma * abs(delta_2_p)**2
                epsilon_n = alpha * abs(delta_0_n)**2 + beta * abs(delta_1_n)**2 + gamma * abs(delta_2_n)**2
            else:
                if abs( s_t[i-1] - s_t_p[i] ) < abs( s_t[i-1] - s_t_n[i] ):
                    positive=True
                    s_t[i] = s_t_p[i]
                else:
                    s_t[i] = s_t_n[i]
    for i in range( t_i ):
        s_t[i] = s_t[-(i+1)]
    s_t = np.roll( s_t, - to_roll )
    spectrum = abs( np.fft.fft( s_t ) )
    spectrum = np.concatenate( ( spectrum[:int(Nf/2)], spectrum[-int(Nf/2):] ) )
    #TODO Why it doesn't require squaring here?
    return spectrum / np.amax( spectrum )
