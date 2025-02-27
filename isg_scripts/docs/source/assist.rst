=========
Assist
=========

The following command is used to analyse assist and charging efficiency taken from PCAN. 
The trace files contains charging or assist.

.. code-block:: python

    {
        "begin_time" : [11, 54, 24],
        "end_time" : [11, 54, 25],
        "Rs" : 33.5,
        "sym_file" : "Symbol_file_isg_assist_codebase.sym",
        "trace_file" : "assist_test_24nov.trc",
        "battery_current" : "IDC_Estimated",
        "battery_voltage" : "Vbat",
        "assist_state" : "Assist_State",
        "ia" : "IA",
        "ib" : "IB",
        "ic" : "IC",
        "charge_state" : "Charging_State",
        "a_or_c" : "a"
    }


Example set of config, trace, and ``.sym`` files are `config.json <_static/files/assist/assistconfig.json>`_, `trace.trc <_static/files/assist/assist_test_24nov.trc>`_ and `symbol.sym <_static/files/Symbol_file_isg_assist_codebase.sym>`_. 


Command below is used to analyse trace taken from PCAN. 

.. code-block:: bash

    isg.assist --config assist.json



Description of config.json file:

* "sym_file" : Name of PCAN ``.sym`` file
* "trace_file" : Name of ``.trc`` file
* "begin_time" : Speed jump in RPM at fire point. Motor-engine specific. 
* "end_time" : Time in seconds required to achieve "vertical_speed_jump" at fire point. 
* "Rs" : Phase resistance in mOhm of the motor
* "a_or_c" : Assist "a" or charging mode "c" 
* "operation_mode" : Op_mode variable name in ``.sym`` file
* "battery_current" : Ibat variable name in ``.sym`` file
* "battery_voltage" : Vbat variable name in ``.sym`` file
* "assist_state" : Assist state variable name in ``.sym`` file
* "charge_state" : Charging state variable name in ``.sym`` file
* "ia" : Phase current A in ``.sym`` file
* "ib" : Phase current B in ``.sym`` file
* "ic" : Phase current C in ``.sym`` file


Energy from battery:

* e_bat = Vbat.Ibat.t

Copper loss:

* e_loss = Rs.(ia^2 + ib^2 + ic^2)t

Efficiency:

* Charging- 

    * eta = -1*e_bat/(-1*e_bat + e_loss)

* Assist-

    * eta = 1 - (e_loss/e_bat)

Voltage ripple, efficiency, energy from battery and copper loss values are printed on command line. 
Sample output is in figure below :

.. image:: _static/images/assist_output.png









