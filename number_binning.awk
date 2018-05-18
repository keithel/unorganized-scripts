BEGIN {
    PROCINFO["sorted_in"]="@ind_num_asc";
    delta = (delta == "") ? 0.1 : delta;
};

/^-?([0-9][0-9]*|[0-9]*(\.[0-9][0-9]*))/ {
    # Special case the [-delta - 0] case so it doesn't bin in the [0-delta] bin
    fractBin=$1/delta
    if (fractBin < 0 && int(fractBin) == fractBin)
        fractBin = fractBin+1
    prefix = (fractBin <= 0 && int(fractBin) == 0) ? "-" : ""
    bins[prefix int(fractBin)]++
}

END {
    for (var in bins)
    {
        srange = sprintf("%0.2f",delta * ((var >= 0) ? var : var-1))
        erange = sprintf("%0.2f",delta * ((var >= 0) ? var+1 : var))
        print srange " " erange " " bins[var]
    }
}
